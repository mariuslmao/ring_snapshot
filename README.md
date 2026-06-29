# Ring Snapshot

Home Assistant custom integration that saves one JPEG snapshot from an existing camera entity by using Home Assistant's internal WebRTC camera API.

This integration does not authenticate with Ring and does not talk to Ring directly. It reuses an already configured Home Assistant camera entity, performs a WebRTC offer/answer handshake, receives one decoded frame with `aiortc`, saves it with Pillow, and immediately closes the peer connection.

## Repository Structure

```text
custom_components/
  ring_snapshot/
    __init__.py
    const.py
    manifest.json
    services.yaml
    strings.json
    translations/
      en.json
```

## Installation

Copy `custom_components/ring_snapshot` into your Home Assistant config directory:

```text
config/custom_components/ring_snapshot
```

Restart Home Assistant.

For HACS custom repositories, add this repository with type `Integration`.

Do not select `AppDaemon`, `App`, `Dashboard`, or `Plugin`. If HACS says this
repository "is not a valid app repository", the wrong repository type was
selected.

## Configuration

After installation, add **Ring Snapshot** in Home Assistant:

```text
Settings -> Devices & services -> Add integration -> Ring Snapshot
```

Alternatively, add the integration domain to `configuration.yaml`:

```yaml
ring_snapshot:
```

The target snapshot directory must be allowed by Home Assistant:

```yaml
homeassistant:
  allowlist_external_dirs:
    - /config/www/snapshots
```

## Service

Call:

```yaml
service: ring_snapshot.take_snapshot
data:
  camera_entity: camera.front_door
  filename: /config/www/snapshots/front_door.jpg
```

Fields:

- `camera_entity`: existing `camera` entity to use
- `filename`: absolute path where the JPEG file will be written

## Requirements

- Home Assistant 2026.x
- A camera entity that exposes WebRTC through Home Assistant
- No Selenium, Playwright, browser automation, or ffmpeg required
