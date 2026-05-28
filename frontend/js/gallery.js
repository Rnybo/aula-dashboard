    let galleryLoaded = false, currentAlbumId = null;
    async function loadGallery() {
      galleryLoaded = true;
      const el = document.getElementById('gallery-content');
      el.innerHTML = '<div class="loading">Henter albums...</div>';
      try {
        const albums = await apiFetch(`/api/gallery/albums?inst_profile_ids=${getChildIds()}`).then(r => r.json());
        renderAlbums(albums);
      } catch(e) { el.textContent = 'Fejl: ' + e.message; }
    }
    function renderAlbums(albums) {
      document.getElementById('gallery-title').textContent = '🖼️ Galleri';
      currentAlbumId = null;
      const el = document.getElementById('gallery-content');
      if (!albums.length) { el.textContent = 'Ingen albums fundet'; return; }
      el.innerHTML = `<div class="albums-grid">${albums.map((a, idx) => {
        const thumb = (a.thumbnailsUrls||[]).find(u => !u.match(/\.mov(\?|$)/i)) || (a.thumbnailsUrls||[])[0];
        const date = a.creationDate ? new Date(a.creationDate).toLocaleDateString('da-DK', {day:'numeric',month:'short',year:'numeric'}) : '';
        const thumbHtml = thumb ? `<img class="album-thumb" src="${thumb}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=album-thumb-placeholder>📷</div>'">` : `<div class="album-thumb-placeholder">📷</div>`;
        return `<div class="album-card" data-idx="${idx}" onclick="openAlbumByIdx(this)">${thumbHtml}
          <div class="album-info"><div class="album-title">${a.title||'Album'}</div><div class="album-date">${date}</div></div></div>`;
      }).join('')}</div>`;
      document.getElementById('gallery-content')._albums = albums;
      // Badge — count albums newer than last seen
      if (currentView !== 'gallery') {
        const seen = getSeen();
        const seenGallery = seen.gallery || 0;
        const newAlbums = albums.filter(a => a.creationDate && new Date(a.creationDate) > new Date(seenGallery)).length;
        setBadge('gallery', newAlbums);
      }
    }
    function openAlbumByIdx(el) {
      const a = (document.getElementById('gallery-content')._albums||[])[parseInt(el.dataset.idx)];
      if (a) openAlbum(a.id, a.title);
    }
    async function openAlbum(albumId, title) {
      currentAlbumId = albumId;
      document.getElementById('gallery-title').textContent = title || 'Album';
      const el = document.getElementById('gallery-content');
      el.innerHTML = `<button class="gallery-back" onclick="loadGallery()">← Alle albums</button><div class="loading">Henter billeder...</div>`;
      try {
        const url = albumId === null ? `/api/gallery/user-media?inst_profile_ids=${getChildIds()}&limit=40` : `/api/gallery/albums/${albumId}/media?inst_profile_ids=${getChildIds()}`;
        renderMedia((await apiFetch(url).then(r => r.json())).results || []);
      } catch(e) { el.innerHTML = `<button class="gallery-back" onclick="loadGallery()">← Alle albums</button><p>Fejl: ${e.message}</p>`; }
    }
    function renderMedia(mediaList) {
      const el = document.getElementById('gallery-content');
      if (!mediaList.length) { el.innerHTML = `<button class="gallery-back" onclick="loadGallery()">← Alle albums</button><p class="loading">Ingen medier</p>`; return; }
      lightboxItems = mediaList.map(m => ({url:m.file?.url||'', thumbUrl:m.largeThumbnailUrl||m.mediumThumbnailUrl||m.thumbnailUrl||m.file?.url||'', isVideo:m.mediaType==='video'||(m.file?.url||'').match(/\.(mov|mp4|webm)/i), title:m.title||m.file?.name||''}));
      el.innerHTML = `<button class="gallery-back" onclick="loadGallery()">← Alle albums</button>
        <div class="media-grid">${lightboxItems.map((item,idx) => `<div class="media-item" onclick="openLightbox(${idx})"><img src="${item.thumbUrl}" loading="lazy" onerror="this.style.opacity='0'">${item.isVideo?'<span class="media-type">▶ Video</span>':''}</div>`).join('')}</div>`;
    }

    // ── Lightbox ──
    function openLightbox(idx) { lightboxIdx=idx; showLightboxItem(); document.getElementById('lightbox').classList.add('open'); }
    function showLightboxItem() {
      const item=lightboxItems[lightboxIdx], med=document.getElementById('lightbox-media');
      med.innerHTML = item.isVideo ? `<video src="${item.url}" controls autoplay style="max-width:92vw;max-height:88vh;border-radius:8px"></video>` : `<img src="${item.url}" alt="${item.title}" onerror="this.src='${item.thumbUrl}'">`;
      document.getElementById('lightbox-caption').textContent = `${lightboxIdx+1} / ${lightboxItems.length}${item.title?' · '+item.title:''}`;
    }
    function lightboxNav(delta) { lightboxIdx=(lightboxIdx+delta+lightboxItems.length)%lightboxItems.length; showLightboxItem(); }
    function closeLightbox(e) { if (!e||e.target===document.getElementById('lightbox')||e.target===document.getElementById('lightbox-close')) document.getElementById('lightbox').classList.remove('open'); }
    document.addEventListener('keydown', e => {
      if (!document.getElementById('lightbox').classList.contains('open')) return;
      if (e.key==='ArrowRight') lightboxNav(1); if (e.key==='ArrowLeft') lightboxNav(-1); if (e.key==='Escape') closeLightbox();
    });
