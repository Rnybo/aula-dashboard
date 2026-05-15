const DASHBOARD_URL = "https://aulanybo.up.railway.app";

// Listen for message from background when session is synced
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "sessionSynced") {
    // Show brief success message then redirect back to dashboard
    const banner = document.createElement("div");
    banner.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #2ecc71;
      color: #fff;
      padding: 14px 28px;
      border-radius: 10px;
      font-size: 1.1rem;
      font-family: sans-serif;
      z-index: 99999;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    `;
    banner.textContent = "✅ Session opdateret! Sender dig tilbage...";
    document.body.appendChild(banner);

    setTimeout(() => {
      window.location.href = DASHBOARD_URL;
    }, 1500);
  }
});
