document.addEventListener('DOMContentLoaded', function () {
  const container = document.getElementById('seatmap');
  if (!container) return;
  const seanceId = container.dataset.seanceId;
  const reserveBtn = document.getElementById('reserveBtn');
  const selectedCountEl = document.getElementById('selectedCount');
  const selectedTotalEl = document.getElementById('selectedTotal');
  const toast = document.getElementById('toast');
  const loadingEl = document.getElementById('seatmapLoading');
  const prixUnitaire = parseFloat(container.dataset.prix || '0');
  setLoading(true);

  function showToast(message, type) {
    const pageMessage = document.getElementById('pageMessage');
    if (pageMessage) {
      pageMessage.textContent = message;
      pageMessage.className = `page-message show ${type || ''}`.trim();
      // scroll to message so user sees it
      setTimeout(() => {
        pageMessage.className = 'page-message';
      }, 4000);
      try {
        window.scrollTo({ top: pageMessage.getBoundingClientRect().top + window.scrollY - 12, behavior: 'smooth' });
      } catch (e) {}
      return;
    }

    if (!toast) {
      alert(message);
      return;
    }
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
      toast.className = 'toast';
    }, 2500);
  }

  function setLoading(isLoading) {
    if (loadingEl) {
      loadingEl.style.display = isLoading ? 'block' : 'none';
    }
  }

  function updateSelectionSummary() {
    const selected = Array.from(document.querySelectorAll('.seat.selected'));
    const count = selected.length;
    const total = count * prixUnitaire;
    if (selectedCountEl) {
      selectedCountEl.textContent = `${count} ${count > 1 ? 'places' : 'place'}`;
    }
    if (selectedTotalEl) {
      selectedTotalEl.textContent = `${total.toFixed(2)} €`;
    }
    if (reserveBtn) {
      reserveBtn.disabled = count === 0;
    }
  }

  fetch(`/seance/${seanceId}/places/`)
    .then(r => r.json())
    .then(data => {
      renderSeatmap(container, data.reserved);
    })
    .catch(() => {
      setLoading(false);
      showToast('Impossible de charger les places réservées', 'error');
    });

  function renderSeatmap(container, reservedIds) {
    // retrieve rows and cols from server-rendered attributes if present in container.dataset
    // For simplicity, fetch seat structure from DOM by calling a lightweight endpoint is omitted.
    // We'll infer by scanning Place elements created server-side; instead request a small JSON of salle config.
    fetch(window.location.pathname + '?_format=json')
      .then(r => r.json())
      .then(cfg => {
        setLoading(false);
        const rows = cfg.nombre_rangees;
        const cols = cfg.nombre_places_par_rangee;
        const aisleStart = Math.ceil(cols / 2) + 1;
        container.style.gridTemplateColumns = `40px repeat(${cols}, 40px)`;
        container.innerHTML = '';

        for (let r = 1; r <= rows; r++) {
          const label = document.createElement('div');
          label.className = 'seat-label';
          label.textContent = String.fromCharCode(64 + r);
          container.appendChild(label);

          for (let c = 1; c <= cols; c++) {
            const seat = document.createElement('div');
            seat.className = 'seat available';
            seat.dataset.rangee = r;
            seat.dataset.numero = c;
            seat.dataset.placeId = cfg.place_map[`${r}-${c}`] || '';
            seat.textContent = c;
            if (c === aisleStart) {
              seat.classList.add('aisle');
            }
            if (seat.dataset.placeId && reservedIds.indexOf(parseInt(seat.dataset.placeId)) !== -1) {
              seat.className = 'seat reserved';
              if (c === aisleStart) {
                seat.classList.add('aisle');
              }
            }
            seat.addEventListener('click', function () {
              if (seat.classList.contains('reserved')) return;
              seat.classList.toggle('selected');
              updateSelectionSummary();
            });
            container.appendChild(seat);
          }
        }
        updateSelectionSummary();
      })
      .catch(() => {
        setLoading(false);
        showToast('Impossible de charger la configuration de la salle', 'error');
      });
  }

  if (!reserveBtn) return;

  reserveBtn.addEventListener('click', function () {
    const selected = Array.from(document.querySelectorAll('.seat.selected'));
    if (selected.length === 0) {
      showToast('Sélectionnez au moins une place', 'error');
      return;
    }
    const places = selected.map(s => parseInt(s.dataset.placeId)).filter(Boolean);
    if (places.length === 0) {
      showToast('Places invalides', 'error');
      return;
    }

    // ensure CSRF token is available
    if (!window.CSRF_TOKEN) {
      showToast('Jeton CSRF manquant — rechargez la page.', 'error');
      return;
    }

    reserveBtn.disabled = true;

    fetch('/reservation/create/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.CSRF_TOKEN
      },
      body: JSON.stringify({seance: seanceId, places: places})
    }).then(r => {
      if (r.status === 401 || r.status === 403) {
        throw new Error('auth');
      }
      return r.json();
    }).then(resp => {
      if (resp.success) {
        showToast('Réservation confirmée — redirection…', 'success');
        setTimeout(() => {
          if (resp.reservation_url) {
            window.location.href = resp.reservation_url;
          } else {
            window.location.reload();
          }
        }, 900);
      } else {
        showToast('Erreur: ' + (resp.error || ''), 'error');
      }
    }).catch((err) => {
      if (err && err.message === 'auth') {
        showToast('Connectez-vous pour réserver', 'error');
        return;
      }
      showToast('Erreur réseau', 'error');
    }).finally(() => {
      reserveBtn.disabled = false;
    });
  });

});
