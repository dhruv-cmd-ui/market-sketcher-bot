# Wealth & Work Flow bot: going live for free

The bot runs on **GitHub Actions**. You need a free GitHub account and no credit card. GitHub starts the bot on a schedule: every 30 minutes from 6 AM to 11 PM IST for news, and every 15 minutes from 5 PM to 9 PM IST on weekdays for FII/DII. Each run does one check and then stops. Between runs nothing is running, so there's no server to maintain.

There are two parts:

1. **Move the bot to GitHub Actions.** Telegram posting works as soon as this is done.
2. **Connect Instagram and Facebook** (optional) so the Reels are published there too.

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
| `MAX_REELS_PER_DAY` | 25 | Reels per day to Instagram/Facebook (Facebook allows 30). On NSE trading days 1 is held for FII/DII until it posts or 9 PM; weekends and NSE holidays give all 25 to news |
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

From then on, each news item and each day's FII/DII update goes out as a Reel on Instagram and Facebook, and as a still card on Telegram.

**Limits:** Instagram allows 100 API posts and Facebook 30 per 24 hours. The bot posts at most 25 Reels a day (`MAX_REELS_PER_DAY`). On NSE trading days, 1 of those is held for the FII/DII Reel. Once the day's Reels are used up, news keeps going to Telegram only, until 11 PM.
