# Wealth & Work Flow bot: going live for free

The bot runs on **GitHub Actions**. You need a free GitHub account and no credit card. GitHub starts the bot on a schedule: every 30 minutes from 6 AM to 11 PM IST for news, and every 15 minutes from 5 PM to 9 PM IST on weekdays for FII/DII. Each run does one check and then stops. Between runs nothing is running, so there's no server to maintain.

There are three parts:

1. **Move the bot to GitHub Actions.** Telegram posting works as soon as this is done.
2. **Connect Instagram and Facebook** (optional) so the Reels and Image Posts are published there too.
3. **Connect YouTube** (optional) so the daily FII/DII Reel is also published as a YouTube Short.

---

## Part 1: GitHub Actions

### Why the repository is public

GitHub gives **public** repositories unlimited free Actions minutes. Private ones get 2,000 minutes a month, which this bot would exceed. The bot needs about 2–3 minutes per news post, and makes up to 34 checks a day.

Public is safe for this project:

- Your keys go into **GitHub Secrets**. They're encrypted, never shown in the code or logs, and not visible to visitors.
- `.env` is never uploaded. This was checked: no key appears in any file that gets published.
- What *is* visible: the code, `history.json` (the list of already-posted links) and run logs (which news was posted).

### 1. Create the repository (on github.com)

1. Sign in, or create a free account at <https://github.com/signup>. No card is asked for.
2. Click **New repository**. Name it, for example, `wealth-workflow-automation`, and choose **Public**. Don't add a README or .gitignore. Click **Create repository**.
3. Copy the repository URL, for example `https://github.com/YOUR_USERNAME/wealth-workflow-automation.git`.

### 2. Upload the code (PowerShell, in `D:\IFT Automation`)

```powershell
git add .
git commit -m "Wealth & Work Flow bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/wealth-workflow-automation.git
git push -u origin main
```

On the first push, a GitHub sign-in window opens in your browser. Approve it.

### 3. Add your keys as Secrets

On the repository page, go to **Settings → Secrets and variables → Actions → New repository secret**. Add each of these, with the same value it has in your local `.env`:

| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | your Gemini key |
| `TELEGRAM_BOT_TOKEN` | your bot token |
| `TELEGRAM_CHAT_ID` | `@wealthandworkflow` |
| `IG_USER_ID`, `FB_PAGE_ID`, `META_ACCESS_TOKEN` | only after Part 2; skip them for now |

### 4. Test the connections (posts nothing)

On the repository page, go to **Actions → Wealth & Work Flow bot → Run workflow**, choose `selftest`, and click **Run workflow**. After about 2 minutes, open the run and the **Run** step. All four lines should say `OK`:

```
OK    Telegram: @wealth_workflow_bot
OK    RSS feeds: {...}
OK    NSE FII/DII: ...
OK    Gemini: key accepted, ...
```

GitHub's servers are in the US. If **NSE** or the **RSS feeds** say `FAIL`, those sites are blocking foreign servers. Tell me and we'll work around it.

### 5. Switch over from this PC

**Only one copy may run at a time**, or every post will appear twice.

The schedule is **off** until you switch it on, so nothing can double-post while the PC copy runs.

1. Stop the bot on this PC.
2. Upload the latest post history, so GitHub doesn't re-post anything:
   ```powershell
   git add history.json
   git commit -m "Latest post history"
   git pull --rebase
   git push
   ```
3. Switch the schedule on: **Settings → Secrets and variables → Actions → Variables tab → New repository variable**. Set the name to `BOT_ENABLED` and the value to `true`.
4. That's it. To try one right away: **Actions → Run workflow → `news`**.

To pause the bot later, change `BOT_ENABLED` to `false`.

### Good to know

- **Timing:** GitHub starts scheduled runs on a best-effort basis, often 5–15 minutes late and occasionally skipped when GitHub is busy. For news and FII/DII polling, that doesn't matter.
- **Run history:** every run appears under the **Actions** tab, with its full log.
- **Reviewing posts:** each run's cards and Reels can be downloaded for 3 days, from the run page under **Artifacts**.
- **Inactivity rule:** GitHub pauses schedules in repositories with no activity for 60 days. Every post commits `history.json`, so this shouldn't happen. If GitHub ever emails you about it, click **Enable workflow** on the Actions tab.
- **Changing settings** (table below): add a line to the `env:` block in `.github/workflows/bot.yml`, for example `MAX_REELS_PER_DAY: 20`, then commit and push.

### Settings

| Setting | Default | Meaning |
|---|---|---|
| `NEWS_WINDOW_START_HOUR` / `NEWS_WINDOW_END_HOUR` | 6 / 23 | News is posted only between 6 AM and 11 PM IST |
| `MAX_NEWS_PER_RUN` | 1 | News posts per 30-minute check. Telegram has no daily cap (SEBI first, then the newest market stories) |
| `NEWS_MAX_AGE_HOURS` | 12 | Older items are skipped (stops a flood of overnight news at 6 AM) |
| `MAX_REELS_PER_DAY` | 25 | Reels+Posts per day to Instagram/Facebook combined (Facebook allows 30). On NSE trading days 2 are held for FII/DII (its Reel + Image Post) until it posts or 9 PM; weekends and NSE holidays give all 25 to news |
| `MAX_NEWS_REELS_PER_DAY` | 4 | News Reels specifically (not Image Posts) per day; once reached, news falls back to Image Posts only, so feeds don't fill with near-identical clips |
| `FII_WINDOW_START_HOUR` / `FII_WINDOW_END_HOUR` | 17 / 21 | FII/DII is checked every 15 minutes between these IST hours on weekdays |

On this PC, the same settings go in `.env`. Restart the bot after editing.

---

## Part 2: Instagram + Facebook

Meta's app review is **not needed**. The app only posts to accounts you own, and that works with the default "Standard Access" while you hold a role on the app. You need three values: `FB_PAGE_ID`, `IG_USER_ID` and `META_ACCESS_TOKEN`.

### A. Accounts

1. Set Instagram to a **Professional account** (Business or Creator): Instagram app → Settings → Account type and tools.
2. **Link Instagram to your Facebook Page**: on Facebook, open the Page → Settings → Linked accounts → Instagram.

### B. Create the Meta app

1. Go to <https://developers.facebook.com/apps> and click **Create app**, logged in with the Facebook account that manages the Page.
2. Choose the use case for **managing a Page and Instagram content** (the wording changes now and then; pick the one covering Pages and Instagram). If you're asked to choose an app type, choose **Business**.
3. In the app dashboard, make sure **Facebook Login for Business** and **Instagram** (Instagram API setup with Facebook Login) are added.

### C. Get the token and IDs

1. Open the **Graph API Explorer**: <https://developers.facebook.com/tools/explorer/>. Select your app, then **User Token**, and tick these permissions:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`.
   Click **Generate Access Token** and approve.
2. Make it long-lived: open the **Access Token Debugger** (<https://developers.facebook.com/tools/debug/accesstoken/>), paste the token, click **Extend Access Token**, and copy the new token.
3. Back in the Explorer, paste the long-lived token and run `GET me/accounts`. For your Page:
   - `id` → **FB_PAGE_ID**
   - `access_token` → **META_ACCESS_TOKEN** (a Page token made from a long-lived token doesn't expire)
4. Run `GET <FB_PAGE_ID>?fields=instagram_business_account` and copy its `id` → **IG_USER_ID**.

### D. Add the values and test

1. Add the three values to your local `.env` and run `.venv\Scripts\python scripts\check_meta.py`. Every line should say `OK`.
2. Add the same three values as GitHub Secrets (Part 1, step 3).

From then on, each news item and each day's FII/DII update goes out as a still card on Telegram, plus Instagram and Facebook posts: news alternates between a Reel and an Image Post (Reel, Post, Reel, Post..., resetting to Reel each morning); FII/DII always posts both a Reel and an Image Post, since it only happens once a day.

**Limits:** Instagram allows 100 API posts and Facebook 30 per 24 hours. The bot posts at most 25 Reels+Posts combined a day (`MAX_REELS_PER_DAY`). On NSE trading days, 2 of those are held for FII/DII's Reel and Image Post. Once the day's Meta slots are used up, news keeps going to Telegram only, until 11 PM.

---

## Part 3: YouTube

Free, no card. Only the **FII/DII Reel** is posted to YouTube (as a Short), once a day on trading days — this isn't tied to the Instagram/Facebook post budget. The title, description and tags are written by the same Gemini call that writes the other captions, with keywords aimed at people searching for daily FII/DII data.

### A. Create a Google Cloud project and enable the API

1. Go to <https://console.cloud.google.com/>, sign in with the Google account for your YouTube channel, and create a new project (any name).
2. Go to **APIs & Services → Library**, search **YouTube Data API v3**, and click **Enable**.

### B. Set up the OAuth consent screen

1. **APIs & Services → OAuth consent screen**. User type: **External**. Fill in an app name and your email, then save through the scopes and test-user screens (you can leave scopes empty here; the script requests the right one directly).
2. On the consent screen's summary page, click **Publish app** so its **Publishing status** says **In production** (not "Testing"). For personal use like this (fewer than 100 users — just you), Google doesn't require you to submit for verification; you'll just see a one-time "Google hasn't verified this app" warning when you approve it in step D below, which is safe to click through. **This step matters**: leaving the app in "Testing" status makes Google expire the refresh token every 7 days, which would silently break YouTube posting every week.

### C. Create OAuth credentials

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **TV and Limited Input devices**. Name it anything.
3. Copy the **Client ID** and **Client Secret** it shows you.

### D. Get the refresh token (one-time, on this PC)

```powershell
cd "D:\IFT Automation"
.venv\Scripts\python scripts\youtube_auth.py
```

It asks for the Client ID and Secret from step C, then prints a URL and a short code. Open the URL, enter the code, sign in with your YouTube channel's Google account, and approve (click through the "unverified app" warning — this is expected, see step B). The script then prints three lines: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.

### E. Add the values

1. Add all three to your local `.env`.
2. Add all three as GitHub Secrets (Part 1, step 3).

From then on, each day's FII/DII Reel also posts to YouTube as a Short (public by default — set `YOUTUBE_PRIVACY_STATUS=unlisted` in `.env`/GitHub Secrets if you'd rather review before making videos public). A custom thumbnail is attempted using the same FII/DII card image; this needs your channel to be **phone-verified** (YouTube Studio → Settings → Channel → Feature eligibility — free, instant). If it isn't verified, the thumbnail step is skipped and logged, but the video still uploads and publishes normally.
