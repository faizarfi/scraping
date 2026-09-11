// MapScraper PRO - Client Side Controller & Interactions

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons
    if (window.lucide) {
        lucide.createIcons();
    }

    // 1. Quick & Multi-Category Chips Selector
    const categoryChips = document.querySelectorAll('.category-chip');
    const queryInput = document.getElementById('query-input');
    const districtInput = document.getElementById('district-input');
    const categorySelect = document.getElementById('category-select');
    const btnSelectAllCats = document.getElementById('btn-select-all-cats');
    const btnResetCats = document.getElementById('btn-reset-cats');
    const selectedCountBadge = document.getElementById('selected-count-badge');

    let selectedCategories = new Set();

    function updateCategoryUI() {
        categoryChips.forEach(chip => {
            const val = chip.getAttribute('data-query');
            if (selectedCategories.has(val)) {
                chip.classList.add('active');
            } else {
                chip.classList.remove('active');
            }
        });

        const arr = Array.from(selectedCategories);
        if (queryInput) {
            queryInput.value = arr.join(', ');
        }
        if (categorySelect) {
            categorySelect.value = arr.length === 1 ? arr[0] : '';
        }

        if (selectedCountBadge) {
            if (arr.length > 0) {
                selectedCountBadge.textContent = `${arr.length} Kategori Terpilih`;
                selectedCountBadge.style.display = 'inline-block';
            } else {
                selectedCountBadge.style.display = 'none';
            }
        }

        if (btnResetCats) {
            btnResetCats.style.display = arr.length > 0 ? 'inline-flex' : 'none';
        }
    }

    categoryChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const queryVal = chip.getAttribute('data-query');
            if (selectedCategories.has(queryVal)) {
                selectedCategories.delete(queryVal);
            } else {
                selectedCategories.add(queryVal);
            }
            updateCategoryUI();
            if (districtInput && !districtInput.value) {
                districtInput.focus();
            }
        });
    });

    if (btnSelectAllCats) {
        btnSelectAllCats.addEventListener('click', () => {
            categoryChips.forEach(chip => {
                selectedCategories.add(chip.getAttribute('data-query'));
            });
            updateCategoryUI();
            showToast('Semua 30 kategori berhasil dipilih sekaligus!', 'info');
        });
    }

    if (btnResetCats) {
        btnResetCats.addEventListener('click', () => {
            selectedCategories.clear();
            updateCategoryUI();
            if (queryInput) queryInput.value = '';
        });
    }

    // 2. Engine Option Card Selector
    const engineCards = document.querySelectorAll('.engine-option-card');
    const apiKeyContainer = document.getElementById('api-key-container');

    engineCards.forEach(card => {
        const radio = card.querySelector('input[type="radio"]');
        if (radio) {
            radio.addEventListener('change', () => {
                engineCards.forEach(c => c.classList.remove('active'));
                if (radio.checked) {
                    card.classList.add('active');
                }
                if (radio.value === 'places_api') {
                    if (apiKeyContainer) apiKeyContainer.style.display = 'block';
                } else {
                    if (apiKeyContainer) apiKeyContainer.style.display = 'none';
                }
                if (window.lucide) lucide.createIcons();
            });
        }
    });

    // 3. Asynchronous Scrape Submission & Live Polling Modal
    const scrapeForm = document.getElementById('scrape-form');
    const modal = document.getElementById('scrape-modal');
    const progressFill = document.getElementById('progress-fill');
    const progressStatus = document.getElementById('progress-status');
    const progressCount = document.getElementById('progress-count');
    const progressTarget = document.getElementById('progress-target');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalStopBtn = document.getElementById('modal-stop-btn');
    const modalViewJobBtn = document.getElementById('modal-view-job-btn');

    let currentActiveJobId = null;

    if (modalStopBtn) {
        modalStopBtn.addEventListener('click', async () => {
            if (!currentActiveJobId) return;

            modalStopBtn.disabled = true;
            modalStopBtn.innerHTML = '<i data-lucide="loader" class="lucide-sm" style="animation: spin 1s linear infinite;"></i><span>Menghentikan...</span>';
            if (window.lucide) lucide.createIcons();

            try {
                const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
                const res = await fetch(`/api/job/${currentActiveJobId}/cancel/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                });
                const resData = await res.json();
                if (resData.success) {
                    showToast(resData.message, 'info');
                }
            } catch (err) {
                console.error('Error stopping job:', err);
                modalStopBtn.disabled = false;
                modalStopBtn.innerHTML = '<i data-lucide="circle-stop" class="lucide-sm"></i><span>Hentikan Scraping</span>';
                if (window.lucide) lucide.createIcons();
            }
        });
    }

    if (scrapeForm) {
        scrapeForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const queryVal = queryInput ? queryInput.value.trim() : '';
            if (!queryVal) {
                showToast('Silakan masukkan kategori atau kata kunci pencarian!', 'warning');
                if (queryInput) queryInput.focus();
                return;
            }

            const formData = new FormData(scrapeForm);
            
            // Tampilkan Modal
            if (modal) {
                modal.classList.add('active');
                if (progressFill) progressFill.style.width = '6%';
                if (progressStatus) progressStatus.textContent = 'Menghubungkan ke engine scraping...';
                if (progressCount) progressCount.textContent = '0';
                if (modalCloseBtn) modalCloseBtn.style.display = 'none';
                if (modalViewJobBtn) modalViewJobBtn.style.display = 'none';
                if (modalStopBtn) {
                    modalStopBtn.style.display = 'inline-flex';
                    modalStopBtn.disabled = false;
                    modalStopBtn.innerHTML = '<i data-lucide="circle-stop" class="lucide-sm"></i><span>Hentikan Scraping</span>';
                }
                if (window.lucide) lucide.createIcons();
            }

            try {
                const response = await fetch('/scrape/start/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                const data = await response.json();
                if (data.success && data.job_id) {
                    currentActiveJobId = data.job_id;
                    pollJobStatus(data.job_id, data.target);
                } else {
                    if (progressStatus) progressStatus.textContent = 'Gagal: ' + (data.error || 'Terjadi kesalahan');
                    if (modalStopBtn) modalStopBtn.style.display = 'none';
                    if (modalCloseBtn) {
                        modalCloseBtn.style.display = 'inline-flex';
                        if (window.lucide) lucide.createIcons();
                    }
                }
            } catch (err) {
                console.error(err);
                if (progressStatus) progressStatus.textContent = 'Error koneksi ke server.';
                if (modalStopBtn) modalStopBtn.style.display = 'none';
                if (modalCloseBtn) {
                    modalCloseBtn.style.display = 'inline-flex';
                    if (window.lucide) lucide.createIcons();
                }
            }
        });
    }

    function pollJobStatus(jobId, targetCount) {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/job/${jobId}/status/`);
                const info = await res.json();

                if (info.error) {
                    clearInterval(interval);
                    if (progressStatus) progressStatus.textContent = info.error;
                    if (modalStopBtn) modalStopBtn.style.display = 'none';
                    if (modalCloseBtn) {
                        modalCloseBtn.style.display = 'inline-flex';
                        if (window.lucide) lucide.createIcons();
                    }
                    return;
                }

                // Update counter & progress bar
                const current = info.total_scraped || 0;
                const target = info.target_count || targetCount || 0;
                if (progressCount) progressCount.textContent = current;
                if (progressTarget) {
                    progressTarget.textContent = (target === 0 || target >= 999) ? 'Maksimal' : target;
                }

                let percent = (target === 0 || target >= 999)
                    ? Math.min(95, 15 + Math.round(current * 2))
                    : Math.min(100, Math.round((current / target) * 100));

                if (info.status === 'running' && percent < 12) percent = 15;
                if (progressFill) progressFill.style.width = `${percent}%`;

                if (info.status === 'running') {
                    if (progressStatus) {
                        if (target === 0 || target >= 999) {
                            progressStatus.textContent = `Mengekstrak seluruh tempat yang tersedia di Google Maps... (${current} didapat)`;
                        } else {
                            progressStatus.textContent = `Sedang mengekstrak tempat... (${current} dari ${target})`;
                        }
                    }
                } else if (info.status === 'completed') {
                    clearInterval(interval);
                    if (modalStopBtn) modalStopBtn.style.display = 'none';
                    if (progressFill) progressFill.style.width = '100%';
                    if (progressStatus) progressStatus.textContent = `Selesai! ${current} tempat berhasil dikumpulkan.`;
                    setTimeout(() => {
                        window.location.href = `/job/${jobId}/`;
                    }, 1200);
                } else if (info.status === 'cancelled') {
                    clearInterval(interval);
                    if (modalStopBtn) modalStopBtn.style.display = 'none';
                    if (modalCloseBtn) modalCloseBtn.style.display = 'inline-flex';
                    if (modalViewJobBtn) {
                        modalViewJobBtn.href = `/job/${jobId}/`;
                        modalViewJobBtn.style.display = 'inline-flex';
                    }
                    if (progressStatus) {
                        progressStatus.textContent = `Scraping dihentikan. ${current} data tempat berhasil disimpan.`;
                    }
                    if (window.lucide) lucide.createIcons();
                    showToast(`Scraping dihentikan oleh pengguna. ${current} data tersimpan.`, 'info');
                } else if (info.status === 'failed') {
                    clearInterval(interval);
                    if (modalStopBtn) modalStopBtn.style.display = 'none';
                    if (progressStatus) progressStatus.textContent = `Gagal: ${info.error_message || 'Terjadi kesalahan sistem'}`;
                    if (modalCloseBtn) {
                        modalCloseBtn.style.display = 'inline-flex';
                        if (window.lucide) lucide.createIcons();
                    }
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 1800);
    }

    if (modalCloseBtn && modal) {
        modalCloseBtn.addEventListener('click', () => {
            modal.classList.remove('active');
            window.location.reload();
        });
    }

    // 4. Professional Toast Notification
    function showToast(message, type = 'info') {
        const existingToast = document.getElementById('app-toast');
        if (existingToast) existingToast.remove();

        const toast = document.createElement('div');
        toast.id = 'app-toast';
        toast.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #1e293b;
            color: #fff;
            padding: 12px 20px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.88rem;
            font-weight: 500;
            z-index: 9999;
            animation: slideIn 0.3s ease;
        `;

        const iconName = type === 'warning' ? 'alert-triangle' : 'check-circle-2';
        toast.innerHTML = `<i data-lucide="${iconName}" style="width: 18px; height: 18px; color: ${type === 'warning' ? '#fbbf24' : '#34d399'};"></i><span>${message}</span>`;
        document.body.appendChild(toast);
        if (window.lucide) lucide.createIcons();

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.4s ease';
            setTimeout(() => toast.remove(), 400);
        }, 3000);
    }

    // 5. Copy Details Helper
    window.copyPlaceInfo = function(name, address, phone) {
        const text = `Nama: ${name}\nAlamat: ${address}\nTelepon: ${phone || '-'}`;
        navigator.clipboard.writeText(text).then(() => {
            showToast('Informasi tempat berhasil disalin ke clipboard!');
        }).catch(err => {
            console.error('Gagal menyalin:', err);
        });
    };

    // 6. Clear All & Deduplication Modal Controller
    const clearAllModal = document.getElementById('clear-all-modal');
    window.openClearAllModal = function() {
        if (clearAllModal) {
            clearAllModal.classList.add('active');
            if (window.lucide) lucide.createIcons();
        }
    };

    window.closeClearAllModal = function() {
        if (clearAllModal) {
            clearAllModal.classList.remove('active');
        }
    };

    if (clearAllModal) {
        clearAllModal.addEventListener('click', (e) => {
            if (e.target === clearAllModal) {
                closeClearAllModal();
            }
        });
    }
});

