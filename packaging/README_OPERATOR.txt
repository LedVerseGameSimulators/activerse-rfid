Activerse RFID - Operator package (central RFID server)
=======================================================

Double-click  "Activerse RFID.exe"  to start the server.
It does everything START_SERVER.bat did: starts the RFID API on port 9000,
serves the reception/admin/leaderboard screens from the same port, and opens
them full screen (Chrome/Edge kiosk).

  Open ..................... http://127.0.0.1:9000/
  Exit full screen ......... Ctrl+Shift+K
  Stop the server .......... double-click STOP_SERVER.bat
  Health check ............. run  "Activerse RFID.exe" --selftest  and send the output

First time on a new PC
----------------------
  1. Start "Activerse RFID.exe". It creates  .env  from  .env.example  and stops.
  2. Open .env in Notepad: set the five game PC IPs (HOOPS_API, LASER_API,
     CLIMB_API, GRID_API, LED_HEX_API) and ADMIN_PASSWORD.
  3. Start "Activerse RFID.exe" again.

Needs on this PC
----------------
  - Google Chrome or Microsoft Edge
  - Network access to the five game PCs (LAN)

Data that belongs to THIS venue (keep it when updating)
-------------------------------------------------------
  .env                the settings you edited above
  data\rfid.sqlite    players, sessions, scores (created on first start; the
                      database upgrades itself automatically - back up
                      data\rfid.sqlite before the first start of a new version)

Updating
--------
  Extract the new release into a NEW folder, then copy your existing .env and
  data\ folder into it. A release zip never contains .env or data\, so extracting
  over the old folder is also safe.

Troubleshooting
---------------
  Logs are in the logs\ folder. Windows SmartScreen may warn about an unsigned
  app: choose "More info" -> "Run anyway".

Developers: ACTIVERSE_KIOSK=0 opens a normal browser window instead of kiosk;
--no-browser starts the server without opening any browser; --console keeps the
console window visible.
