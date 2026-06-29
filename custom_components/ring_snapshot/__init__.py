"""Take one JPEG snapshot from an existing WebRTC camera entity."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection
from aiortc import RTCSessionDescription
from aiortc.sdp import candidate_from_sdp, candidate_to_sdp
from homeassistant.components import camera
from homeassistant.components.camera import Camera
from homeassistant.components.camera.const import StreamType
from homeassistant.components.camera.helper import get_camera_from_entity_id
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.util.ulid import ulid
import voluptuous as vol
from webrtc_models import RTCIceCandidateInit

from .const import (
    ATTR_CAMERA_ENTITY,
    ATTR_FILENAME,
    DOMAIN,
    SERVICE_TAKE_SNAPSHOT,
    SNAPSHOT_TIMEOUT,
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CAMERA_ENTITY): cv.entity_id,
        vol.Required(ATTR_FILENAME): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Ring Snapshot integration."""

    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ring Snapshot from a config entry."""

    _async_register_services(hass)
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    if hass.services.has_service(DOMAIN, SERVICE_TAKE_SNAPSHOT):
        return

    async def take_snapshot(call: ServiceCall) -> None:
        await _async_take_snapshot(
            hass,
            call.data.get(ATTR_CAMERA_ENTITY)
            or _async_get_configured_camera_entity(hass),
            call.data[ATTR_FILENAME],
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TAKE_SNAPSHOT,
        take_snapshot,
        schema=SERVICE_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Ring Snapshot config entry."""

    return True


def _async_get_configured_camera_entity(hass: HomeAssistant) -> str:
    """Return the configured default camera entity."""

    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        camera_entity = entry.options.get(ATTR_CAMERA_ENTITY) or entry.data.get(
            ATTR_CAMERA_ENTITY
        )
        if camera_entity:
            return camera_entity

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="camera_entity_required",
    )


async def _async_take_snapshot(
    hass: HomeAssistant,
    camera_entity_id: str,
    filename: str,
) -> None:
    """Take one decoded frame from the camera's WebRTC stream and save it."""

    snapshot_path = Path(filename)
    if not snapshot_path.is_absolute():
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="filename_not_absolute",
            translation_placeholders={CONF_FILENAME: filename},
        )

    if not hass.config.is_allowed_path(str(snapshot_path)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="filename_not_allowed",
            translation_placeholders={CONF_FILENAME: str(snapshot_path)},
        )

    registry = er.async_get(hass)
    registry_entry = registry.async_get(camera_entity_id)
    if registry_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_registered",
            translation_placeholders={"entity_id": camera_entity_id},
        )

    if registry_entry.domain != camera.DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_camera",
            translation_placeholders={"entity_id": camera_entity_id},
        )

    camera_entity = get_camera_from_entity_id(hass, camera_entity_id)
    if camera_entity is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_loaded",
            translation_placeholders={"entity_id": camera_entity_id},
        )

    if (
        StreamType.WEB_RTC
        not in camera_entity.camera_capabilities.frontend_stream_types
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="webrtc_not_supported",
            translation_placeholders={"entity_id": camera_entity_id},
        )

    await _async_snapshot_from_webrtc(hass, camera_entity, snapshot_path)


async def _async_snapshot_from_webrtc(
    hass: HomeAssistant,
    camera_entity: Camera,
    snapshot_path: Path,
) -> None:
    """Perform a WebRTC handshake and persist exactly one video frame."""

    pc = RTCPeerConnection(_async_rtc_configuration(camera_entity))
    frame_future: asyncio.Future[Any] = hass.loop.create_future()
    session_id = ulid()

    @pc.on("track")
    def _on_track(track: Any) -> None:
        if track.kind != "video" or frame_future.done():
            return

        hass.async_create_task(_async_receive_first_frame(track, frame_future))

    @pc.on("icecandidate")
    def _on_icecandidate(candidate: Any) -> None:
        if candidate is None:
            return

        hass.async_create_task(
            _async_send_local_candidate(camera_entity, session_id, candidate)
        )

    def _handle_webrtc_message(message: Any) -> None:
        hass.async_create_task(
            _async_handle_webrtc_message(pc, message, frame_future)
        )

    pc.addTransceiver("video", direction="recvonly")

    try:
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await camera_entity.async_handle_async_webrtc_offer(
            pc.localDescription.sdp,
            session_id,
            _handle_webrtc_message,
        )

        frame = await asyncio.wait_for(frame_future, timeout=SNAPSHOT_TIMEOUT)
        image = frame.to_image()
        await hass.async_add_executor_job(
            _save_jpeg,
            image,
            snapshot_path,
        )
    except asyncio.TimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="snapshot_timeout",
            translation_placeholders={"entity_id": camera_entity.entity_id},
        ) from err
    finally:
        await pc.close()
        camera_entity.close_webrtc_session(session_id)


async def _async_receive_first_frame(
    track: Any,
    frame_future: asyncio.Future[Any],
) -> None:
    """Receive exactly one decoded frame from a video track."""

    try:
        frame_future.set_result(await track.recv())
    except Exception as err:  # pragma: no cover - aiortc transport-specific errors.
        if not frame_future.done():
            frame_future.set_exception(err)


async def _async_send_local_candidate(
    camera_entity: Camera,
    session_id: str,
    candidate: Any,
) -> None:
    """Forward a local aiortc ICE candidate to the camera integration."""

    await camera_entity.async_on_webrtc_candidate(
        session_id,
        RTCIceCandidateInit.from_dict(
            {
                "candidate": f"candidate:{candidate_to_sdp(candidate)}",
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex,
            }
        ),
    )


async def _async_handle_webrtc_message(
    pc: RTCPeerConnection,
    message: Any,
    frame_future: asyncio.Future[Any],
) -> None:
    """Apply a WebRTC answer or remote ICE candidate from Home Assistant."""

    answer = getattr(message, "answer", None)
    if answer is not None:
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type="answer"))
        return

    candidate = getattr(message, "candidate", None)
    if candidate is not None:
        await _add_ice_candidate(pc, candidate)
        return

    code = getattr(message, "code", None)
    if code is not None and not frame_future.done():
        error_message = getattr(message, "message", code)
        frame_future.set_exception(HomeAssistantError(error_message))


async def _add_ice_candidate(pc: RTCPeerConnection, candidate: Any) -> None:
    """Convert a Home Assistant WebRTC candidate into an aiortc candidate."""

    candidate_text = _candidate_value(candidate, "candidate")
    if not candidate_text:
        return

    if candidate_text.startswith("candidate:"):
        candidate_text = candidate_text.removeprefix("candidate:")

    rtc_candidate = candidate_from_sdp(candidate_text)
    rtc_candidate.sdpMid = _candidate_value(candidate, "sdpMid")
    if rtc_candidate.sdpMid is None:
        rtc_candidate.sdpMid = _candidate_value(candidate, "sdp_mid")
    sdp_mline_index = _candidate_value(candidate, "sdpMLineIndex")
    if sdp_mline_index is None:
        sdp_mline_index = _candidate_value(candidate, "sdp_m_line_index")
    rtc_candidate.sdpMLineIndex = sdp_mline_index

    await pc.addIceCandidate(rtc_candidate)


def _candidate_value(candidate: Any, key: str) -> Any:
    """Return a candidate value from either an object or dict."""

    if isinstance(candidate, dict):
        return candidate.get(key)
    return getattr(candidate, key, None)


def _async_rtc_configuration(camera_entity: Camera) -> RTCConfiguration | None:
    """Translate Home Assistant's WebRTC client config for aiortc."""

    client_config = camera_entity.async_get_webrtc_client_configuration()
    configuration = getattr(client_config, "configuration", None)
    if configuration is None:
        return None

    ice_servers = _get_value(configuration, "ice_servers", "iceServers") or []
    return RTCConfiguration(
        iceServers=[_rtc_ice_server(server) for server in ice_servers]
    )


def _rtc_ice_server(server: Any) -> RTCIceServer:
    """Convert a Home Assistant ICE server object or dict into aiortc form."""

    return RTCIceServer(
        urls=_get_value(server, "urls"),
        username=_get_value(server, "username"),
        credential=_get_value(server, "credential"),
    )


def _get_value(source: Any, *keys: str) -> Any:
    """Read the first present attribute or mapping key."""

    for key in keys:
        if isinstance(source, dict) and key in source:
            return source[key]
        if hasattr(source, key):
            return getattr(source, key)
    return None


def _save_jpeg(image: Any, snapshot_path: Path) -> None:
    """Save a Pillow image as JPEG."""

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(snapshot_path, format="JPEG", quality=95)
