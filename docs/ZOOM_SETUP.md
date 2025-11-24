# Zoom Integration Setup Guide

This guide walks you through setting up Zoom API integration for the MCP Snapshot Server, enabling you to list, download, and process Zoom meeting transcripts directly.

## Prerequisites

- A Zoom account with administrative access
- Access to [Zoom Marketplace](https://marketplace.zoom.us/)
- The MCP Snapshot Server installed and configured

## Table of Contents

1. [Creating a Server-to-Server OAuth App](#creating-a-server-to-server-oauth-app)
2. [Obtaining Credentials](#obtaining-credentials)
3. [Configuring Required Scopes](#configuring-required-scopes)
4. [Setting Environment Variables](#setting-environment-variables)
5. [Testing Your Configuration](#testing-your-configuration)
6. [Troubleshooting](#troubleshooting)

---

## Creating a Server-to-Server OAuth App

### Step 1: Access Zoom Marketplace

1. Navigate to [https://marketplace.zoom.us/](https://marketplace.zoom.us/)
2. Click **Sign In** in the top right corner
3. Log in with your Zoom account credentials

### Step 2: Create a New App

1. Click **Develop** dropdown in the top navigation
2. Select **Build App**
3. Choose **Server-to-Server OAuth** as the app type
4. Click **Create**

### Step 3: App Information

1. **App Name**: Enter a descriptive name (e.g., "MCP Snapshot Server")
2. **Short Description**: Brief description of your app
3. **Company Name**: Your company or organization name
4. **Developer Contact**: Your email address
5. **Would you like to publish this app on Zoom Marketplace?**: Select **No** (unless you plan to publish publicly)
6. Click **Continue**

---

## Obtaining Credentials

After creating your app, you'll see the **App Credentials** page with three critical pieces of information:

### Account ID
- Located at the top of the credentials page
- Format: `abc123XYZ...`
- Copy this value - you'll need it for `ZOOM_ACCOUNT_ID`

### Client ID
- Listed as "Client ID" on the credentials page
- Format: Alphanumeric string
- Copy this value - you'll need it for `ZOOM_CLIENT_ID`

### Client Secret
- Listed as "Client Secret" on the credentials page
- Click **Copy** to copy the secret
- ⚠️ **IMPORTANT**: Store this securely - it won't be shown again
- Copy this value - you'll need it for `ZOOM_CLIENT_SECRET`

---

## Configuring Required Scopes

Scopes define what your app can access in Zoom. The MCP Snapshot Server requires the following scopes:

### Step 1: Navigate to Scopes

1. In your app configuration, click on the **Scopes** tab
2. Click **+ Add Scopes**

### Step 2: Add Required Scopes

Add the following scopes one at a time:

| Scope | Description | Why It's Needed |
|-------|-------------|-----------------|
| `recording:read:admin` | View all user recordings | Required to access meeting recordings |
| `cloud_recording:read:list_user_recordings:admin` | List user recordings | Required to list recordings by date |
| `cloud_recording:read:list_recording_files:admin` | View recording files | **Required to download transcript files** |
| `cloud_recording:read:list_recording_files` | View recording files | **Required to access individual recording files** |
| `user:read:user:admin` | Read user information | Required for user context |
| `user:read:list_users:admin` | List users | Required for multi-user support |

⚠️ **IMPORTANT**: The two `cloud_recording:read:list_recording_files` scopes are **critical** for downloading transcripts. Without these, you'll get a "Missing required scopes" error when attempting to download.

### Step 3: Save Scopes

1. After adding all scopes, click **Done**
2. Click **Continue** at the bottom of the page

### Step 4: Activation

1. In the **Activation** tab, toggle the **Activate your app** button to **ON**
2. Your app is now active and ready to use

---

## Setting Environment Variables

### Step 1: Copy .env.example

If you haven't already, create your `.env` file:

```bash
cp .env.example .env
```

### Step 2: Configure Zoom Credentials

Open `.env` in your text editor and update the Zoom section:

```bash
# Zoom API Configuration (Required for Zoom integration)
ZOOM_ACCOUNT_ID=your_actual_account_id_here
ZOOM_CLIENT_ID=your_actual_client_id_here
ZOOM_CLIENT_SECRET=your_actual_client_secret_here

# Zoom API Settings (Optional - defaults shown)
ZOOM_DEFAULT_USER_ID=me
ZOOM_API_TIMEOUT=30
ZOOM_MAX_RETRIES=3

# Zoom Caching Settings (Optional - defaults shown)
ZOOM_CACHE_TTL_SECONDS=900
ZOOM_MAX_CACHE_SIZE=100
```

### Configuration Details

- **ZOOM_ACCOUNT_ID**: Account ID from App Credentials page
- **ZOOM_CLIENT_ID**: Client ID from App Credentials page
- **ZOOM_CLIENT_SECRET**: Client Secret from App Credentials page (keep this secure!)
- **ZOOM_DEFAULT_USER_ID**: User ID to fetch recordings for (default: "me" = authenticated user)
- **ZOOM_API_TIMEOUT**: HTTP request timeout in seconds (default: 30)
- **ZOOM_MAX_RETRIES**: Number of retry attempts for failed API calls (default: 3)
- **ZOOM_CACHE_TTL_SECONDS**: How long to cache recordings list (default: 900 = 15 minutes)
- **ZOOM_MAX_CACHE_SIZE**: Maximum number of cached recordings lists (default: 100)

### Security Best Practices

⚠️ **NEVER commit your `.env` file to version control!**

- Ensure `.env` is in your `.gitignore` file
- For production deployments, use secure secrets management:
  - **AWS**: AWS Secrets Manager
  - **Azure**: Azure Key Vault
  - **Google Cloud**: Secret Manager
  - **Kubernetes**: Sealed Secrets or External Secrets Operator

---

## Testing Your Configuration

### Step 1: Verify Configuration

Run the server and check for configuration warnings:

```bash
uv run python -m mcp_snapshot_server.server
```

If credentials are missing or incomplete, you'll see an error like:
```
ValueError: Incomplete Zoom credentials. If configuring Zoom, you must provide ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, and ZOOM_CLIENT_SECRET
```

### Step 2: Test Zoom Connection

Use the MCP client or Claude Desktop to test the Zoom integration:

```
# List your Zoom recordings
list_zoom_recordings

# List recordings from a specific date range
list_zoom_recordings(from_date="2024-11-01", to_date="2024-11-24")

# Search for meetings by topic
list_zoom_recordings(search_query="customer")
```

### Step 3: Fetch a Transcript

```
# Get the meeting_id from list_zoom_recordings output
fetch_zoom_transcript(meeting_id="123456789")
# Returns: transcript://abc123
```

This fetches the transcript from Zoom and caches it in server memory. The returned URI can be used for:
- Generating snapshots
- Querying directly in your conversations

### Step 4: Use the Transcript

**Option A: Generate a Snapshot**
```
# Single-step: Fetch and generate snapshot
generate_snapshot_from_zoom(meeting_id="123456789", output_format="markdown")

# OR Two-step: Fetch first, then generate
1. fetch_zoom_transcript(meeting_id="123456789")
   # Returns transcript://abc123
2. generate_customer_snapshot(transcript_uri="transcript://abc123", output_format="json")
```

**Option B: Query Directly**
```
# After fetching, you can ask questions about the transcript
"What were the main concerns raised in transcript://abc123?"
"Who attended the meeting in transcript://abc123?"
"Summarize the action items from transcript://abc123"
```

The transcript is exposed as an MCP Resource, allowing Claude to read and analyze it directly.

---

## Troubleshooting

### Error: "Zoom API credentials not configured"

**Problem**: The server can't find your Zoom credentials.

**Solution**:
1. Verify your `.env` file exists in the project root
2. Check that all three credentials are set:
   ```bash
   grep ZOOM_ .env
   ```
3. Ensure no extra spaces or quotes around the values
4. Restart the server after updating `.env`

### Error: "Failed to initialize Zoom client"

**Problem**: The credentials are invalid or the app is not activated.

**Solution**:
1. Double-check your credentials in the Zoom Marketplace
2. Verify your app is **Activated** in the Activation tab
3. Regenerate Client Secret if needed (in App Credentials tab)
4. Update `.env` with new credentials

### Error: "No VTT transcript found for meeting"

**Problem**: The meeting doesn't have a transcript available.

**Solution**:
1. **Check if transcript feature is enabled**:
   - Go to Zoom Settings → Recording
   - Enable "Audio transcript" setting
2. **Verify the meeting was recorded**:
   - Only cloud recordings have transcripts
   - Local recordings don't support transcripts
3. **Check if transcript is still processing**:
   - Transcripts can take up to 24 hours to process
   - Large meetings take longer

### Error: "Transcript is still processing"

**Problem**: Zoom is still generating the transcript.

**Solution**:
- Wait and try again later (transcripts typically process within 2x meeting duration)
- Check the recording in Zoom web interface to see processing status

### Error: "Missing required scopes" (HTTP 400)

**Problem**: Your OAuth app doesn't have the necessary permissions to access recording files.

**Error Details**:
```
Zoom API error 400 (code: 124): Access token does not contain scopes:
[cloud_recording:read:list_recording_files, cloud_recording:read:list_recording_files:admin]
```

**Solution**:
1. Go to [Zoom Marketplace](https://marketplace.zoom.us/)
2. Navigate to **Develop** → **Build App** → select your app
3. Click on the **Scopes** tab
4. Add the missing scopes:
   - `cloud_recording:read:list_recording_files`
   - `cloud_recording:read:list_recording_files:admin`
5. Click **Done** and **Continue**
6. In the **Activation** tab, ensure the app is still **Activated**
7. **IMPORTANT**: You may need to **deactivate** and **reactivate** the app for scope changes to take effect
8. Restart your MCP server and try again

### Error: "Forbidden" or "401 Unauthorized"

**Problem**: Insufficient permissions or invalid authentication.

**Solution**:
1. Verify all required scopes are added to your app (see table above)
2. Check that your app is activated
3. Regenerate your Client Secret and update `.env`
4. Verify your Zoom account has permission to access recordings
5. Try deactivating and reactivating the app to refresh permissions

### Recordings List is Empty

**Problem**: No recordings found in the specified date range.

**Solution**:
1. Verify meetings were recorded to the cloud (not locally)
2. Check the date range covers when meetings occurred
3. Ensure "Audio transcript" was enabled during the meetings
4. Try expanding the date range:
   ```
   list_zoom_recordings(from_date="2024-01-01", to_date="2024-12-31")
   ```

### Cache Issues

**Problem**: Recordings list shows old data.

**Solution**:
- Wait for cache to expire (15 minutes by default)
- OR adjust `ZOOM_CACHE_TTL_SECONDS` in `.env`:
  ```bash
  ZOOM_CACHE_TTL_SECONDS=0  # Disable caching
  ZOOM_CACHE_TTL_SECONDS=300  # 5 minutes
  ```
- Restart the server after changing cache settings

---

## API Rate Limits

Zoom API has rate limits to prevent abuse:

- **Requests per second**: Varies by account type
- **Daily quota**: Typically sufficient for normal use

The MCP Snapshot Server implements:
- Automatic retry with exponential backoff
- 15-minute caching to minimize API calls
- Configurable retry attempts

If you hit rate limits:
1. Increase `ZOOM_CACHE_TTL_SECONDS` to cache longer
2. Reduce frequency of `list_zoom_recordings` calls
3. Contact Zoom to increase your rate limit

---

## Language Support

**Current Limitation**: Zoom currently only provides English transcripts.

If your meetings are in other languages:
- Transcripts may be incomplete or unavailable
- Consider Zoom's roadmap for multi-language support
- Alternative: Use third-party transcription services

---

## Additional Resources

- [Zoom API Documentation](https://developers.zoom.us/docs/api/)
- [Zoom Server-to-Server OAuth Guide](https://developers.zoom.us/docs/internal-apps/s2s-oauth/)
- [Zoom Recording API Reference](https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#tag/Cloud-Recording)
- [Zoom Marketplace Support](https://marketplace.zoom.us/support)

---

## Security Checklist

Before deploying to production:

- [ ] `.env` file is in `.gitignore`
- [ ] Client Secret is stored securely (not in code)
- [ ] Using secrets management service in production
- [ ] Zoom app activation is completed
- [ ] All required scopes are configured
- [ ] API timeout is appropriate for your network
- [ ] Cache TTL is set appropriately for your use case
- [ ] Logging is configured (check for credential leaks in logs)

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [MCP Snapshot Server GitHub Issues](https://github.com/YOUR_REPO/issues)
2. Review Zoom API logs in Zoom Marketplace (App Management → Your App → API Logs)
3. Contact Zoom Developer Support through the Marketplace

