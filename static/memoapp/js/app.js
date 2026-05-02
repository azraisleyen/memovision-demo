/**
 * =========================================================
 * MemoVision Frontend Core (Production Ready)
 * =========================================================
 *
 * ✔ Server-driven (Django)
 * ✔ Page-based initialization
 * ✔ No SPA logic
 * ✔ No global side-effects
 *
 * Bu dosya sadece:
 * - Upload preview
 * - Thumbnail generation
 * - Flash messages
 *
 * yönetir.
 */

document.addEventListener("DOMContentLoaded", () => {
    initPage();
});


/* =========================================================
   PAGE ROUTER
========================================================= */

function initPage() {
    const page = document.body.dataset.page;

    switch (page) {
        case "new-analysis":
            initUploadPreview();
            initAnalysisSubmitLoading();
            break;

        case "dashboard":
            initFlashMessages();
            initDashboardInteractions();
            break;

        default:
            // Landing vb.
            break;
    }
}


/* =========================================================
   UPLOAD PREVIEW (NEW ANALYSIS ONLY)
========================================================= */

function initUploadPreview() {

    const fileInput = document.getElementById("id_original_video");
    if (!fileInput) return;

    /* DOM ELEMENTS */
    const previewWrapper = document.getElementById("localPreviewWrapper");
    const previewImage = document.getElementById("localThumbPreview");

    const fileNameEl = document.getElementById("selectedFileName");
    const fileStatusEl = document.getElementById("selectedFileStatus");

    const posterStage = document.getElementById("videoPosterStage");
    const playBtn = document.getElementById("posterPlayButton");
    const bottomPlayBtn = document.getElementById("bottomPlayButton");
    const resetBtn = document.getElementById("resetPreviewButton");

    const playerWrapper = document.getElementById("localVideoPlayerWrapper");
    const videoPlayer = document.getElementById("localVideoPlayer");

    const urlInput = document.getElementById("id_source_url");
    const urlBtn = document.getElementById("urlAddButton");

    let objectUrl = null;


    /* =====================================================
        FILE SELECT HANDLER
    ===================================================== */
    fileInput.addEventListener("change", async (e) => {

        const file = e.target.files[0];
        if (!file) return;

        resetUrlMode();
        cleanupObjectUrl();

        objectUrl = URL.createObjectURL(file);

        /* Player setup */
        videoPlayer.src = objectUrl;
        videoPlayer.load();

        /* UI update */
        previewWrapper.classList.remove("hidden");

        fileNameEl.textContent = file.name;
        fileStatusEl.textContent = "Video seçildi. Oynatmaya hazır.";

        posterStage.classList.remove("hidden");
        playerWrapper.classList.add("hidden");

        try {
            const preview = await generateThumbnail(file);

            previewImage.src = preview.thumbnail;
            setDuration(preview.duration);

        } catch (err) {
            console.error("Thumbnail error:", err);
            fileStatusEl.textContent = "Önizleme oluşturulamadı.";
        }
    });


    /* =====================================================
        VIDEO PLAY / RESET
    ===================================================== */

    function playVideo() {
        if (!videoPlayer.src) return;

        posterStage.classList.add("hidden");
        playerWrapper.classList.remove("hidden");

        videoPlayer.play().catch(() => {});
    }

    function resetVideo() {
        videoPlayer.pause();

        posterStage.classList.remove("hidden");
        playerWrapper.classList.add("hidden");
    }

    playBtn?.addEventListener("click", playVideo);
    bottomPlayBtn?.addEventListener("click", playVideo);
    resetBtn?.addEventListener("click", resetVideo);


    /* =====================================================
        URL MODE
    ===================================================== */

    urlBtn?.addEventListener("click", () => {

        const url = urlInput.value.trim();

        if (!isValidUrl(url)) {
            alert("Geçerli bir video URL girin.");
            return;
        }

        /* File mode reset */
        fileInput.value = "";
        cleanupObjectUrl();

        /* Player reset */
        videoPlayer.pause();
        videoPlayer.removeAttribute("src");
        videoPlayer.load();

        previewWrapper.classList.add("hidden");

        fileNameEl.textContent = "URL kaynağı seçildi";
        fileStatusEl.textContent = "Video backend tarafından işlenecek.";
    });


    /* =====================================================
        CLEANUP
    ===================================================== */

    function cleanupObjectUrl() {
        if (objectUrl) {
            URL.revokeObjectURL(objectUrl);
            objectUrl = null;
        }
    }

    function resetUrlMode() {
        if (urlInput) {
            urlInput.value = "";
        }
    }
}



function initAnalysisSubmitLoading() {
    const form = document.getElementById("analysisForm");
    const loadingBox = document.getElementById("analysisLoading");
    if (!form || !loadingBox) return;

    form.addEventListener("submit", () => {
        const submitBtn = form.querySelector("button[type=\"submit\"]");
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Analiz İşleniyor...";
        }
        loadingBox.classList.remove("hidden");
    });
}

/* =========================================================
   THUMBNAIL GENERATION
========================================================= */

function generateThumbnail(file) {

    return new Promise((resolve, reject) => {

        const video = document.createElement("video");
        const canvas = document.createElement("canvas");

        const url = URL.createObjectURL(file);

        video.src = url;
        video.preload = "metadata";
        video.muted = true;
        video.playsInline = true;

        /* Metadata loaded */
        video.onloadedmetadata = () => {
            video.currentTime = Math.min(0.1, video.duration / 10);
        };

        /* Frame ready */
        video.onseeked = () => {
            try {
                canvas.width = video.videoWidth || 640;
                canvas.height = video.videoHeight || 360;

                const ctx = canvas.getContext("2d");
                ctx.drawImage(video, 0, 0);

                const thumbnail = canvas.toDataURL("image/jpeg");
                const duration = formatDuration(video.duration);

                URL.revokeObjectURL(url);

                resolve({ thumbnail, duration });

            } catch (e) {
                reject(e);
            }
        };

        video.onerror = () => {
            URL.revokeObjectURL(url);
            reject(new Error("Video thumbnail oluşturulamadı."));
        };
    });
}


/* =========================================================
   FLASH MESSAGES
========================================================= */

function initFlashMessages() {

    const messages = document.querySelectorAll(".message-item");
    if (!messages.length) return;

    setTimeout(() => {
        messages.forEach(el => {
            el.style.opacity = "0";
            el.style.transform = "translateY(-8px)";
        });
    }, 2500);
}


/* =========================================================
   UTILITIES
========================================================= */

function formatDuration(seconds) {
    const s = Math.max(0, Math.floor(seconds || 0));
    const m = Math.floor(s / 60);
    const r = s % 60;

    return `${m}:${String(r).padStart(2, "0")}`;
}

function setDuration(text) {
    const el = document.getElementById("posterDurationBadge");
    if (el) el.textContent = text;
}

function isValidUrl(url) {
    return url.startsWith("http://") || url.startsWith("https://");
}

function initDashboardInteractions() {
    const video = document.getElementById("analysisVideo");
    const items = document.querySelectorAll(".dm-suggestion-btn");
    const narrative = document.getElementById("agentNarrative");
    items.forEach((item) => {
        item.addEventListener("click", () => {
            const seek = parseFloat(item.dataset.seek || "0");
            if (video && !Number.isNaN(seek)) {
                video.currentTime = seek;
                video.play().catch(() => {});
            }
            if (narrative) narrative.textContent = item.dataset.agent || "Öneri detayı bulunamadı.";
        });
    });

    const printBtn = document.getElementById("printReportBtn");
    printBtn?.addEventListener("click", () => window.print());

    const refreshBtn = document.getElementById("refreshAnalysisBtn");
    refreshBtn?.addEventListener("click", () => window.location.reload());

    const resetBtn = document.getElementById("resetAnalysisBtn");
    resetBtn?.addEventListener("click", () => {
        if (video) {
            video.pause();
            video.currentTime = 0;
        }
        if (narrative) narrative.textContent = "Bir öneriye tıklayarak zaman bazlı agent açıklamasını görüntüleyin.";
    });
}
