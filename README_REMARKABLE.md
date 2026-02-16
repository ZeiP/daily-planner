# reMarkable Cloud Integration (ddvk/rmapi)

To enable automatic PDF uploads to your reMarkable, this project uses the `rmapi` tool.
**Important:** You must use the community-maintained `ddvk/rmapi` fork, as the original project is archived and incompatible with the current reMarkable Cloud API.

## 1. Install `rmapi`

1.  **Download the latest release** from the **ddvk/rmapi** repository:
    https://github.com/ddvk/rmapi/releases

2.  Download the appropriate binary for your system (e.g., `rmapi-linuxx86-64.tar.gz`).

3.  **Install**:
    ```bash
    tar -xzf rmapi-linuxx86-64.tar.gz
    chmod +x rmapi
    sudo mv rmapi /usr/local/bin/
    # Or move to ~/bin and ensure it's in your PATH
    ```

4.  **Verify**:
    ```bash
    rmapi version
    ```
    (It should be v0.0.28 or later).

## 2. Authenticate

Run `rmapi` once to set up authentication:

```bash
rmapi ls
```

- This will prompt you to visit `https://my.remarkable.com/device/browser/connect`.
- Log in and copy the one-time code.
- Paste the code into the terminal.

Once you see a file listing, you are authenticated.

## 3. Usage

The planner will now automatically upload generated PDFs:

```bash
python -m planner --skip-caldav
```

Troubleshooting:
- If uploads fail with "auth" errors, re-run `rmapi ls` to refresh your token.
