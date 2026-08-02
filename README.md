# Wing Delivery for Home Assistant

Monitor your [Wing](https://wing.com/) drone deliveries in Home Assistant:
delivery status, ETA, an "active delivery" flag, the drone's live position on
the map, and a status-change event for automations.

> This is an **unofficial** integration. It is not affiliated with, endorsed by,
> or supported by Wing or Google. It reads your Wing order emails and, for live
> tracking, an undocumented tracking endpoint that may change or break without
> notice.

## Installation (HACS)

1. In HACS, add this repository as a custom repository (category: Integration),
   or install it from the default store once listed.
2. Restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> "Wing Delivery".

## Configuration

All setup is in the UI. You provide the mailbox that receives your Wing order
emails:

- IMAP host and port (Gmail: `imap.gmail.com`, `993`)
- Username and password (Gmail requires an app password)
- Mailbox folder (default `INBOX`)
- Wing sender filter (default `wing.com`)
- Poll interval in seconds

Nothing is stored outside Home Assistant.

## Entities

- `sensor.wing_delivery_status` - ordered / preparing / en_route / arriving / delivered
- `sensor.wing_delivery_eta` - minutes to arrival (live deliveries)
- `binary_sensor.wing_delivery_active` - a delivery is in progress
- `device_tracker.wing_drone` - drone position on the map (live deliveries)

## Automations

Listen for the `wing_delivery_status_changed` event:

```yaml
automation:
  - alias: Announce drone arriving
    trigger:
      - platform: event
        event_type: wing_delivery_status_changed
        event_data:
          new_status: arriving
    action:
      - service: tts.google_translate_say
        data:
          entity_id: media_player.kitchen
          message: "Your Wing drone is arriving."
```

## Status

ETA and drone position require the live tracking layer, finalized once real
delivery traffic is captured. Until then the integration reports status from
your order emails.
