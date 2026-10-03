(() => {
    "use strict";

    // The content-script match remains limited to https://www.instagram.com/*.
    // Ignore the home page and avoid adding duplicate controls.
    if (window.location.pathname === "/" ||
        document.querySelector(".instagram-extension-box")) return;

    let collectedInstagramImages = [];
    const markedImages = new WeakSet();
    const style = document.createElement("style");
    style.textContent = `
        .instagram-extension-box { position: fixed; bottom: 10px; right: 10px; width: 260px; background-color: white; border-radius: 3px; color: #5a5a5a; padding: 15px; text-align: center; border: 1px solid #e0e0e0; }
        .instagram-extension-box-button { display: inline-block; background-color: #adadad; color: white; border-radius: 5px; padding: 10px; margin: 3px 0; }
        .instagram-extension-box-button.faded { background-color: #dedddd; }
        .instagram-extension-box-button:hover { background-color: #e2ba7b; cursor: pointer; }
        #instagram-extension-box-title { display: block; margin: 3px 0; font-weight: bold; }
        #instagram-extension-box-description { display: block; margin: 6px 0; font-size: 11px; line-height: 1.4; }
    `;
    document.head.append(style);
    const box = document.createElement("div");
    box.className = "instagram-extension-box";
    // Static extension-owned text; image URLs and page text never become HTML.
    box.innerHTML = `
        <span id="instagram-extension-box-title">Instagram download extension</span>
        <span id="instagram-extension-box-description">Scroll down the profile to make all photos visible, then collect the photos and simply download them in one click.</span>
        <span id="instagram-extension-box-button-collect" class="instagram-extension-box-button" role="button" tabindex="0">Collect</span>
        <span id="instagram-extension-box-button-download" class="instagram-extension-box-button faded" role="button" tabindex="0">Download photos</span>
    `;
    document.body.append(box);
    const collectButton = box.querySelector("#instagram-extension-box-button-collect");
    const downloadButton = box.querySelector("#instagram-extension-box-button-download");

    function markCollected(img) {
        img.style.opacity = "0.2";
        if (markedImages.has(img)) return;
        markedImages.add(img);
        const rect = img.getBoundingClientRect();
        const marker = document.createElement("div");
        marker.className = "instagram-extension-marker";
        marker.textContent = "Collected";
        Object.assign(marker.style, {
            position: "absolute",
            top: `${rect.top + window.scrollY + 4}px`,
            left: `${rect.left + window.scrollX + 4}px`,
            backgroundColor: "#444", borderRadius: "25px", padding: "6px",
            fontSize: "12px", color: "white", pointerEvents: "none"
        });
        document.body.append(marker);
        const animation = marker.animate([{ opacity: 1 }, { opacity: 0 }], 4000);
        animation.onfinish = () => {
            marker.remove();
            markedImages.delete(img);
        };
    }

    collectButton.addEventListener("click", () => {
        // A fresh snapshot on every click: removed/replaced images don't accumulate.
        const uniqueUrls = new Set();
        document.querySelectorAll("body img").forEach(img => {
            if (!img.getAttribute("src")) return;
            const url = new URL(img.src, document.baseURI);
            // An image URL must not become an executable/script download link.
            if (!["http:", "https:"].includes(url.protocol)) return;
            uniqueUrls.add(url.href);
            markCollected(img);
        });
        collectedInstagramImages = [...uniqueUrls];
        downloadButton.textContent = `Download ${collectedInstagramImages.length} photos`;
        downloadButton.classList.toggle("faded", collectedInstagramImages.length === 0);
    });

    downloadButton.addEventListener("click", () => {
        const name = document.querySelector("body h1")?.textContent || "instagram";
        for (const link of collectedInstagramImages) {
            const anchor = document.createElement("a");
            anchor.href = link;
            anchor.download = `${name}.jpg`;
            document.body.append(anchor);
            anchor.click();
            anchor.remove();
        }
    });

    for (const button of [collectButton, downloadButton]) {
        button.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                button.click();
            }
        });
    }
})();
