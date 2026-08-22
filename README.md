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
- Wing sender filter (default `wing.google.com` — Wing order receipts come from `noreply@wing.google.com`)
- New-order email check interval (default `120` seconds) — how often the mailbox is checked for a new order
- Live tracking update interval (default `20` seconds) — how often the ETA and drone position refresh while a delivery is in the air

Nothing is stored outside Home Assistant.

### Polling

The two intervals are independent. When nothing is being delivered, the
integration just checks your mailbox every *email* interval. Once an order is
active, it speeds up to the *live* interval to keep the ETA and the drone's map
position current — but your mailbox is still only checked at the (slower) email
interval, so a fast live interval doesn't hammer Gmail. Set the email interval
high (checking for orders is infrequent) and the live interval low (say 15–30s)
for a smooth-moving map without extra email logins.

### Gmail app password

If your Gmail account has 2-Step Verification enabled, Gmail blocks your normal
password over IMAP and you must use an **app password** (otherwise setup fails
with "Application-specific password required"):

1. Go to <https://myaccount.google.com/apppasswords> (this page only works when
   2-Step Verification is on for your account).
2. Enter a name such as `Home Assistant Wing` and click **Create**.
3. Google shows a 16-character password in four groups (for example
   `abcd efgh ijkl mnop`). Copy it.
4. In the integration, set the **username** to your full email address and the
   **password** to this app password (the spaces are optional).

Other IMAP providers work too — use their host, port, and a normal or
provider-specific password as appropriate.

## Entities

- `sensor.wing_delivery_status` - ordered / preparing / en_route / arriving / delivered
- `sensor.wing_delivery_eta` - minutes to arrival (live deliveries)
- `binary_sensor.wing_delivery_active` - a delivery is in progress
- `device_tracker.wing_drone` - drone position on the map (live deliveries)

The `sensor.wing_delivery_status` entity also exposes attributes: `order_id`,
`items` (the ordered item names, parsed from the receipt email), `tracking_url`,
and `last_update`. In practice Wing goes straight from `en_route` to
`delivered`, so the `arriving` state is rarely (if ever) emitted.

## Automations

Listen for the `wing_delivery_status_changed` event:

```yaml
automation:
  - alias: Announce Wing delivery
    trigger:
      - platform: event
        event_type: wing_delivery_status_changed
        event_data:
          new_status: delivered
    action:
      - service: tts.google_translate_say
        data:
          entity_id: media_player.kitchen
          message: "Your Wing order has been delivered."
```

## How it works

Order status and the item list come from your Wing receipt emails. Live ETA and
the drone's position come from Wing's order-tracking service (the same feed the
`myorder.wing.com` page uses), reached with the tracking id from the email — no
Wing login required.

## Buy me a coffee

Did you find this helpful? Consider supporting additional development:

<a href="https://www.buymeacoffee.com/ajachiernoo" target="_blank">
  <img src="https://raw.githubusercontent.com/ajachierno/WingTracker/main/brand/bmc_button.png" alt="Buy me a coffee" height="50">
</a>

<br><br>

<a href="https://www.buymeacoffee.com/ajachiernoo" target="_blank">
  <img src="https://raw.githubusercontent.com/ajachierno/WingTracker/main/brand/buymeacoffee_qr.png" alt="Buy me a coffee QR code" width="200">
</a>
