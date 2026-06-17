# Deploying to Oracle Cloud (Always Free)

This runs the bot 24/7 for free on a small Linux VM. You do it once; after
that it posts every day on its own, survives reboots, and restarts if it
crashes. Steps marked **[on your Mac]** run in your Mac's Terminal; steps
marked **[on the server]** run after you SSH in.

---

## 1. Create the free VM

1. Sign up at <https://cloud.oracle.com> (it asks for a card to verify
   identity but does **not** charge for Always Free resources).
2. Menu (☰) → **Compute → Instances → Create instance**.
3. Settings:
   - **Name:** `wordbot` (anything).
   - **Image:** Canonical **Ubuntu** (22.04 or 24.04).
   - **Shape:** click **Change shape** → **Ampere**… or simplest, the
     **Always Free–eligible** `VM.Standard.E2.1.Micro` (AMD). Look for the
     green **"Always Free eligible"** label — pick one that has it.
   - **SSH keys:** choose **Generate a key pair for me** and click
     **Save private key** (you'll get a `.key` file — keep it safe). Or
     upload your own public key if you have one.
4. Click **Create**. After a minute it shows a **Public IP address** — copy it.

A Discord bot only makes *outbound* connections, so you do **not** need to
open any inbound ports.

---

## 2. Copy the project to the server  **[on your Mac]**

Replace `KEY.key` with the path to the private key you saved, and `PUBLIC_IP`
with your instance's IP. This copies the project (skipping the Mac-only
`.venv` and IDE files) including your `.env`, so your token comes along:

```bash
rsync -av --exclude '.venv' --exclude '.idea' --exclude '__pycache__' \
  -e "ssh -i KEY.key" \
  ~/PyCharmMiscProject/ ubuntu@PUBLIC_IP:~/wordbot/
```

If `rsync` asks about authenticity the first time, type `yes`.

---

## 3. Set up Python on the server  **[on the server]**

SSH in:

```bash
ssh -i KEY.key ubuntu@PUBLIC_IP
```

Then install Python and the dependencies:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
cd ~/wordbot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Quick test (should log "Logged in as ..."), then press **Ctrl+C** to stop:

```bash
.venv/bin/python bot.py
```

---

## 4. Run it as an always-on service  **[on the server]**

Install the included service file so it runs in the background, on boot, and
auto-restarts:

```bash
sudo cp ~/wordbot/deploy/wordbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wordbot
```

Check it's running and watch the logs:

```bash
sudo systemctl status wordbot
journalctl -u wordbot -f      # live logs; Ctrl+C to stop watching
```

You should see `Daily Word of the Day scheduled for 10:00 AM America/Chicago.`
That's it — the bot is now live 24/7.

---

## Everyday commands  **[on the server]**

```bash
sudo systemctl restart wordbot   # restart it
sudo systemctl stop wordbot      # turn it off
sudo systemctl start wordbot     # turn it back on
journalctl -u wordbot -n 50      # last 50 log lines
```

## Updating the bot later

Re-run the `rsync` command from step 2 to push your latest code, then:

```bash
sudo systemctl restart wordbot
```

## Notes

- The manual `word` terminal trigger doesn't apply on the server (there's no
  interactive console under systemd) — but the daily 10 AM post runs on its
  own. To trigger a post by hand, run the bot locally on your Mac.
- The post time is pinned to `America/Chicago` in code, so the server's own
  timezone doesn't matter.
