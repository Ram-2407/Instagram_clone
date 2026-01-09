// Global toast container (add this div once in base.html body or create if missing)
(function ensureToastContainer() {
  if (!document.getElementById('toastContainer')) {
    const tc = document.createElement('div');
    tc.id = 'toastContainer';
    tc.className = 'position-fixed end-0 bottom-0 p-3';
    tc.style.zIndex = '1080';
    document.body.appendChild(tc);
  }
})();

document.addEventListener('DOMContentLoaded', () => {
  // Likes (optimistic UI + error handling)
  document.querySelectorAll('.like-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const postId = btn.dataset.post;
      const countEl = btn.querySelector('.like-count');
      const originalCount = countEl ? parseInt(countEl.textContent, 10) || 0 : 0;
      const wasLiked = btn.classList.contains('btn-danger');

      // Optimistic toggle
      btn.classList.toggle('btn-outline-danger', wasLiked);
      btn.classList.toggle('btn-danger', !wasLiked);
      if (countEl) countEl.textContent = String(originalCount + (wasLiked ? -1 : 1));

      try {
        const res = await fetch(`/api/like/${postId}/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrf() }
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        // Reconcile with server
        if (countEl) countEl.textContent = String(data.count);
        btn.classList.toggle('btn-outline-danger', !data.liked);
        btn.classList.toggle('btn-danger', data.liked);
      } catch (err) {
        console.error(err);
        // Rollback optimistic update
        btn.classList.toggle('btn-outline-danger', !wasLiked);
        btn.classList.toggle('btn-danger', wasLiked);
        if (countEl) countEl.textContent = String(originalCount);
        showToast('Error', 'Could not update like. Please try again.');
      }
    });
  });

  // Comments (error handling)
  document.querySelectorAll('.comment-form').forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const postId = form.dataset.post;
      const input = form.querySelector('input[name="text"]');
      const text = (input.value || '').trim();
      if (!text) return;

      try {
        const res = await fetch(`/api/comment/${postId}/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCsrf()
          },
          body: new URLSearchParams({ text })
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        input.value = '';
        const list = document.getElementById(`comments-${postId}`);
        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.innerHTML = `<strong>@${escapeHtml(data.author)}</strong> ${escapeHtml(data.text)} <small class="text-muted float-end">just now</small>`;
        list.prepend(li);

        const parent = form.closest('.card-body');
        const countEl = parent.querySelector('.comment-count');
        if (countEl) countEl.textContent = data.count;
      } catch (err) {
        console.error(err);
        showToast('Error', 'Could not post comment. Please try again.');
      }
    });
  });

  // Follow/Unfollow (optimistic UI + error handling)
  document.querySelectorAll('.follow-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const username = btn.dataset.username;
      const originalText = btn.textContent.trim();
      const willFollow = originalText.toLowerCase() === 'follow';
      btn.disabled = true;
      btn.textContent = willFollow ? 'Unfollowing…' : 'Following…';

      try {
        const res = await fetch(`/api/follow/${username}/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrf() }
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        btn.textContent = data.following ? 'Unfollow' : 'Follow';
      } catch (err) {
        console.error(err);
        btn.textContent = originalText; // rollback
        showToast('Error', 'Could not update follow. Please try again.');
      } finally {
        btn.disabled = false;
      }
    });
  });

  // Notifications WebSocket
  const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws';
  let notifCount = 0;
  const badge = document.getElementById('notifBadge');
  const notifSocket = new WebSocket(`${wsScheme}://${location.host}/ws/notif/`);

  notifSocket.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      showToast(d.title || 'Activity', d.text || '');
      notifCount += 1;
      if (badge) {
        badge.textContent = String(notifCount);
        badge.style.display = 'inline-block';
      }
    } catch (err) {
      console.error('Notif parse error', err);
    }
  };
  notifSocket.onclose = () => console.warn('Notifications socket closed');

  // Story viewer modal logic + playback reset
  const storyModal = document.getElementById('storyModal');
  if (storyModal) {
    storyModal.addEventListener('show.bs.modal', event => {
      const trigger = event.relatedTarget;
      if (!trigger) return;
      const mediaUrl = trigger.getAttribute('data-media');
      const user = trigger.getAttribute('data-user') || '';
      document.getElementById('storyUser').textContent = user ? '@' + user : '';

      const imgEl = document.getElementById('storyImage');
      const vidEl = document.getElementById('storyVideo');

      // Defensive: if no media URL present, show a helpful toast and abort
      if (!mediaUrl) {
        if (imgEl) imgEl.classList.add('d-none');
        if (vidEl) { vidEl.classList.add('d-none'); vidEl.src = ''; }
        showToast('Error', 'Story media not available');
        return;
      }

      // Video case
      if (/\.(mp4|webm|mov)$/i.test(mediaUrl)) {
        if (imgEl) imgEl.classList.add('d-none');
        if (vidEl) {
          vidEl.classList.remove('d-none');
          // reload source to ensure playback works across browsers
          vidEl.pause();
          vidEl.src = mediaUrl;
          vidEl.muted = true;
          try { vidEl.load(); } catch (e) {}
          vidEl.play().catch(() => {});
        }
      } else {
        // Image case
        if (vidEl) { vidEl.classList.add('d-none'); vidEl.src = ''; }
        if (imgEl) {
          imgEl.classList.remove('d-none');
          imgEl.src = mediaUrl;
        }
      }
    });

    storyModal.addEventListener('hidden.bs.modal', () => {
      const imgEl = document.getElementById('storyImage');
      const vidEl = document.getElementById('storyVideo');
      if (vidEl) {
        try { vidEl.pause(); } catch {}
        vidEl.currentTime = 0;
        vidEl.src = '';
      }
      if (imgEl) imgEl.src = '';
    });
  }

  // Expose a small helper to reset the notifications badge when entering the notifications page
  window.resetNotifBadge = function () {
    if (badge) {
      notifCount = 0;
      badge.textContent = '0';
      badge.style.display = 'none';
    }
  };
});

// CSRF helper
function getCsrf() {
  const name = 'csrftoken=';
  const cookies = document.cookie.split(';');
  for (let c of cookies) {
    c = c.trim();
    if (c.startsWith(name)) return c.substring(name.length);
  }
  const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
  return input ? input.value : '';
}

// Safely escape user-provided text
function escapeHtml(str) {
  const map = {
    '&': '&amp;', '<': '&lt;', '>': '&gt;',
    '"': '&quot;', "'": '&#039;'
  };
  return String(str).replace(/[&<>"']/g, s => map[s]);
}

// Toasts (append to global container)
function showToast(title, body) {
  const container = document.getElementById('toastContainer');
  const toastEl = document.createElement('div');
  toastEl.className = 'toast show mb-2';
  toastEl.innerHTML = `
    <div class="toast-header">
      <strong class="me-auto">${escapeHtml(title)}</strong>
      <small>just now</small>
      <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
    </div>
    <div class="toast-body">${escapeHtml(body)}</div>
  `;
  container.appendChild(toastEl);
  setTimeout(() => { try { toastEl.remove(); } catch {} }, 4000);
}