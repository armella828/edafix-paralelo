const API_BASE = window.location.port === '3000' ? ('http://' + window.location.hostname + ':8000') : '';
const MAX_IMAGES = 10;

const apiBadge = document.getElementById('apiBadge');
if (apiBadge) {
  const host = window.location.hostname;
  apiBadge.textContent = (host === 'localhost' || host === '127.0.0.1' || !host)
    ? 'localhost:8000'
    : host;
}

// ---------- Tabs ----------
const tabs = document.querySelectorAll('[data-tab]');
const panels = document.querySelectorAll('[data-tab-panel]');
const activeTabClasses = ['bg-gradient-to-r', 'from-emerald-600', 'to-teal-600', 'text-white', 'shadow-lg', 'shadow-emerald-950/60'];
const inactiveTabClasses = ['text-slate-400', 'hover:text-white', 'hover:bg-white/5'];

tabs.forEach(btn => {
  btn.addEventListener('click', () => {
    tabs.forEach(b => {
      b.classList.remove(...activeTabClasses);
      b.classList.add(...inactiveTabClasses);
    });
    btn.classList.remove(...inactiveTabClasses);
    btn.classList.add(...activeTabClasses);

    panels.forEach(p => { p.classList.add('hidden'); });
    const panel = document.getElementById('panel-' + btn.dataset.tab);
    if (panel) panel.classList.remove('hidden');
  });
});

// ---------- Tab 1: Analizar suelo (1 a 10 imágenes en paralelo) ----------
const dropzone = document.getElementById('dropzone');
const dropzoneContent = document.getElementById('dropzoneContent');
const previewContainer = document.getElementById('previewContainer');
const previewGrid = document.getElementById('previewGrid');
const soilFile = document.getElementById('soilFile');
const soilFolder = document.getElementById('soilFolder');
const btnDropzoneUpload = document.getElementById('btnDropzoneUpload');
const btnDropzoneFolder = document.getElementById('btnDropzoneFolder');
const btnAnalyze = document.getElementById('btnAnalyze');
const btnAnalyzeIcon = document.getElementById('btnAnalyzeIcon');
const btnAnalyzeLabel = document.getElementById('btnAnalyzeLabel');
const btnAddMore = document.getElementById('btnAddMore');
const btnAddMoreLabel = document.getElementById('btnAddMoreLabel');
const btnPickFolder = document.getElementById('btnPickFolder');
const btnResetPhoto = document.getElementById('btnResetPhoto');
const pickerModal = document.getElementById('pickerModal');
const pickerModalSub = document.getElementById('pickerModalSub');
const pickerModalCounter = document.getElementById('pickerModalCounter');
const pickerModalGrid = document.getElementById('pickerModalGrid');
const btnPickerClose = document.getElementById('btnPickerClose');
const btnPickerCancel = document.getElementById('btnPickerCancel');
const btnPickerConfirm = document.getElementById('btnPickerConfirm');
const btnPickerSelectAll = document.getElementById('btnPickerSelectAll');
const btnPickerClear = document.getElementById('btnPickerClear');
const selectionCounter = document.getElementById('selectionCounter');
const selectionProgressBar = document.getElementById('selectionProgressBar');
const limitNotice = document.getElementById('limitNotice');
const farmerErrorBanner = document.getElementById('farmerErrorBanner');
const resultFarmer = document.getElementById('resultFarmer');
const parcelNameInput = document.getElementById('parcelName');
const btnDownloadReport = document.getElementById('btnDownloadReport');
const managementPlanBox = document.getElementById('managementPlanBox');
const managementPlanContext = document.getElementById('managementPlanContext');
const managementPlanGrid = document.getElementById('managementPlanGrid');
const historySection = document.getElementById('historySection');
const historyList = document.getElementById('historyList');
const btnClearHistory = document.getElementById('btnClearHistory');

const HISTORY_KEY = 'edafix_history_v1';
const MAX_HISTORY_ITEMS = 8;

const ICON_BOLT = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>';
const ICON_SPINNER = '<svg class="w-4 h-4 spinner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="9" stroke-opacity="0.25" /><path d="M21 12a9 9 0 0 0-9-9" /></svg>';

let lastAnalysisContext = null;
let selectedItems = [];

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function showLimitNotice(message) {
  if (!message) {
    limitNotice.classList.add('hidden');
    limitNotice.textContent = '';
    return;
  }
  limitNotice.textContent = message;
  limitNotice.classList.remove('hidden');
}

function showFarmerError(message) {
  if (!message) {
    farmerErrorBanner.classList.add('hidden');
    farmerErrorBanner.textContent = '';
    return;
  }
  farmerErrorBanner.textContent = '❌ ' + message;
  farmerErrorBanner.classList.remove('hidden');
}

function openFilePicker() {
  if (selectedItems.length >= MAX_IMAGES) {
    showLimitNotice('⚠️ Ya tienes ' + MAX_IMAGES + ' imágenes cargadas. Quita alguna si deseas agregar otra.');
    return;
  }
  soilFile.value = '';
  soilFile.click();
}

function updateSelectionUI() {
  const count = selectedItems.length;
  selectionCounter.textContent = count + ' / ' + MAX_IMAGES + ' imágenes';
  if (selectionProgressBar) {
    selectionProgressBar.style.width = ((count / MAX_IMAGES) * 100) + '%';
  }
  selectionCounter.className = count > 0
    ? 'text-xs font-mono font-semibold px-3 py-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/35 text-emerald-300'
    : 'text-xs font-mono font-semibold px-3 py-1.5 rounded-full bg-slate-900/90 border border-white/10 text-slate-300';

  if (count === 0) {
    previewContainer.classList.add('hidden');
    dropzoneContent.classList.remove('hidden');
    btnAnalyze.disabled = true;
    btnAnalyzeIcon.innerHTML = ICON_BOLT;
    btnAnalyzeLabel.textContent = 'Analizar Suelo en Paralelo';
    btnAddMore.classList.remove('hidden');
    btnAddMoreLabel.textContent = 'Cargar imágenes';
    btnPickFolder.classList.remove('hidden');
    btnResetPhoto.classList.add('hidden');
    previewGrid.innerHTML = '';
    return;
  }

  dropzoneContent.classList.add('hidden');
  previewContainer.classList.remove('hidden');
  btnAnalyze.disabled = false;
  btnAnalyzeIcon.innerHTML = ICON_BOLT;
  btnAnalyzeLabel.textContent = count === 1
    ? 'Analizar 1 Imagen en Paralelo'
    : 'Analizar ' + count + ' Imágenes en Paralelo';
  btnResetPhoto.classList.remove('hidden');

  if (count < MAX_IMAGES) {
    btnAddMore.classList.remove('hidden');
    btnAddMoreLabel.textContent = 'Cargar más fotos';
    btnPickFolder.classList.remove('hidden');
  } else {
    btnAddMore.classList.add('hidden');
    btnPickFolder.classList.add('hidden');
  }

  previewGrid.className = count === 1
    ? 'flex justify-center'
    : 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3';

  previewGrid.innerHTML = selectedItems.map((item, idx) => {
    const cardClass = count === 1
      ? 'relative w-full max-w-md rounded-2xl overflow-hidden border border-white/15 bg-slate-950 shadow-xl'
      : 'relative rounded-xl overflow-hidden border border-white/10 bg-slate-950 group/card shadow-md hover:border-emerald-500/40 transition';
    const imgClass = count === 1
      ? 'w-full max-h-72 object-cover'
      : 'w-full h-28 object-cover group-hover/card:scale-105 transition-transform duration-300';
    return (
      '<div class="' + cardClass + '">' +
      '<div class="overflow-hidden relative">' +
      '<img src="' + item.url + '" alt="Muestra ' + (idx + 1) + '" class="' + imgClass + '" />' +
      '<div class="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-slate-950/90 to-transparent pointer-events-none"></div>' +
      '</div>' +
      '<span class="absolute top-2 left-2 text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-slate-950/85 text-emerald-300 border border-white/15 backdrop-blur">#' + (idx + 1) + '</span>' +
      '<button type="button" data-remove-id="' + item.id + '" title="Quitar imagen" ' +
      'class="absolute top-2 right-2 w-6 h-6 rounded-full bg-slate-950/85 hover:bg-red-500 text-slate-200 hover:text-white text-xs font-bold flex items-center justify-center border border-white/15 backdrop-blur transition">✕</button>' +
      '<div class="px-2.5 py-1.5 text-[11px] text-slate-300 truncate bg-slate-950/95 border-t border-white/5" title="' + escapeHtml(item.file.name) + '">' + escapeHtml(item.file.name) + '</div>' +
      '</div>'
    );
  }).join('');
}

let pickerCandidates = [];
let pickerSelectedSet = new Set();

function closePickerModal() {
  pickerCandidates.forEach(c => URL.revokeObjectURL(c.url));
  pickerCandidates = [];
  pickerSelectedSet.clear();
  pickerModalGrid.innerHTML = '';
  pickerModal.classList.add('hidden');
}

function renderPickerModal() {
  const available = MAX_IMAGES - selectedItems.length;
  const chosen = pickerSelectedSet.size;
  pickerModalSub.textContent = 'Haz clic en las fotos que quieras incluir (puedes elegir hasta ' + available + ' imagen' + (available === 1 ? '' : 'es') + ' más).';
  pickerModalCounter.textContent = chosen + ' / ' + available + ' seleccionadas';
  btnPickerConfirm.disabled = chosen === 0;
  btnPickerConfirm.textContent = chosen > 0 ? ('Agregar ' + chosen + ' imagen' + (chosen === 1 ? '' : 'es')) : 'Agregar seleccionadas';

  pickerModalGrid.innerHTML = pickerCandidates.map((item, idx) => {
    const isChecked = pickerSelectedSet.has(idx);
    const borderCls = isChecked
      ? 'border-emerald-400 ring-2 ring-emerald-400/50 bg-emerald-950/30'
      : 'border-white/10 hover:border-white/30 bg-slate-950/80';
    const checkCls = isChecked
      ? 'bg-emerald-500 text-slate-950 border-emerald-400'
      : 'bg-slate-950/80 text-transparent border-white/30';
    return (
      '<button type="button" data-pick-idx="' + idx + '" class="text-left rounded-xl overflow-hidden border transition relative group ' + borderCls + '">' +
      '<div class="relative h-28 bg-slate-950 overflow-hidden">' +
      '<img src="' + item.url + '" alt="' + escapeHtml(item.file.name) + '" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" />' +
      '<span class="absolute top-2 right-2 w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-extrabold transition ' + checkCls + '">✓</span>' +
      '</div>' +
      '<div class="px-2.5 py-1.5 text-[11px] text-slate-200 truncate" title="' + escapeHtml(item.file.name) + '">' + escapeHtml(item.file.name) + '</div>' +
      '</button>'
    );
  }).join('');
}

function openPickerModal(imageFiles) {
  const available = MAX_IMAGES - selectedItems.length;
  if (available <= 0) {
    showLimitNotice('⚠️ Ya alcanzaste el máximo de ' + MAX_IMAGES + ' imágenes. Quita alguna para agregar otra.');
    return;
  }
  closePickerModal();
  pickerCandidates = imageFiles.map(file => ({ file, url: URL.createObjectURL(file) }));
  pickerSelectedSet = new Set();
  renderPickerModal();
  pickerModal.classList.remove('hidden');
}

pickerModalGrid.addEventListener('click', e => {
  const card = e.target.closest('[data-pick-idx]');
  if (!card) return;
  const idx = Number(card.dataset.pickIdx);
  const available = MAX_IMAGES - selectedItems.length;
  if (pickerSelectedSet.has(idx)) {
    pickerSelectedSet.delete(idx);
  } else {
    if (pickerSelectedSet.size >= available) {
      showLimitNotice('⚠️ Solo puedes marcar hasta ' + available + ' imagen(es) más (máximo 10 en total).');
      return;
    }
    pickerSelectedSet.add(idx);
  }
  renderPickerModal();
});

btnPickerSelectAll.addEventListener('click', () => {
  const available = MAX_IMAGES - selectedItems.length;
  pickerSelectedSet = new Set();
  for (let i = 0; i < Math.min(available, pickerCandidates.length); i++) {
    pickerSelectedSet.add(i);
  }
  renderPickerModal();
});

btnPickerClear.addEventListener('click', () => {
  pickerSelectedSet.clear();
  renderPickerModal();
});

btnPickerConfirm.addEventListener('click', () => {
  const chosenFiles = Array.from(pickerSelectedSet)
    .sort((a, b) => a - b)
    .map(i => pickerCandidates[i].file);
  closePickerModal();
  if (chosenFiles.length > 0) {
    addFiles(chosenFiles, false);
  }
});

btnPickerClose.addEventListener('click', closePickerModal);
btnPickerCancel.addEventListener('click', closePickerModal);

function addFiles(fileList, allowModalOnOverflow = true) {
  showFarmerError('');
  const incoming = Array.from(fileList || []).filter(f => {
    if (f.type && f.type.startsWith('image/')) return true;
    return /\.(jpe?g|png|webp|bmp|jfif)$/i.test(f.name || '');
  });
  if (incoming.length === 0) {
    showLimitNotice('⚠️ No se encontraron archivos de imagen válidos (.jpg, .png, .webp, .bmp).');
    return;
  }

  const available = MAX_IMAGES - selectedItems.length;
  if (available <= 0) {
    showLimitNotice('⚠️ Ya alcanzaste el máximo de ' + MAX_IMAGES + ' imágenes. Quita alguna para agregar otra.');
    return;
  }

  // Si seleccionó más imágenes que el cupo disponible, abrir selector visual con 1 clic
  if (allowModalOnOverflow && incoming.length > available) {
    openPickerModal(incoming);
    return;
  }

  const toAdd = incoming.slice(0, available);
  toAdd.forEach(file => {
    selectedItems.push({
      id: Math.random().toString(36).slice(2, 10) + Date.now().toString(36),
      file,
      url: URL.createObjectURL(file),
    });
  });

  showLimitNotice('');
  resultFarmer.classList.add('hidden');
  updateSelectionUI();
}

function clearSelection() {
  selectedItems.forEach(item => URL.revokeObjectURL(item.url));
  selectedItems = [];
  soilFile.value = '';
  soilFolder.value = '';
  showLimitNotice('');
  showFarmerError('');
  resultFarmer.classList.add('hidden');
  updateSelectionUI();
}

previewGrid.addEventListener('click', e => {
  const btn = e.target.closest('[data-remove-id]');
  if (!btn) return;
  e.stopPropagation();
  const id = btn.dataset.removeId;
  const target = selectedItems.find(item => item.id === id);
  if (target) URL.revokeObjectURL(target.url);
  selectedItems = selectedItems.filter(item => item.id !== id);
  showLimitNotice('');
  showFarmerError('');
  resultFarmer.classList.add('hidden');
  updateSelectionUI();
});

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
  dropzone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
});
dropzone.addEventListener('dragover', () => dropzone.classList.add('border-emerald-400', 'bg-emerald-500/10'));
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('border-emerald-400', 'bg-emerald-500/10'));
dropzone.addEventListener('drop', e => {
  dropzone.classList.remove('border-emerald-400', 'bg-emerald-500/10');
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    addFiles(e.dataTransfer.files);
  }
});

// Evitar doble disparo cuando se hace clic en <label> dentro del dropzone
btnDropzoneUpload.addEventListener('click', e => {
  e.stopPropagation();
  if (selectedItems.length >= MAX_IMAGES) {
    e.preventDefault();
    showLimitNotice('⚠️ Ya tienes ' + MAX_IMAGES + ' imágenes cargadas. Quita alguna si deseas agregar otra.');
  }
});
btnDropzoneFolder.addEventListener('click', e => {
  e.stopPropagation();
  if (selectedItems.length >= MAX_IMAGES) {
    e.preventDefault();
    showLimitNotice('⚠️ Ya tienes ' + MAX_IMAGES + ' imágenes cargadas. Quita alguna si deseas agregar otra.');
  }
});
btnAddMore.addEventListener('click', e => {
  if (selectedItems.length >= MAX_IMAGES) {
    e.preventDefault();
    showLimitNotice('⚠️ Ya tienes ' + MAX_IMAGES + ' imágenes cargadas. Quita alguna si deseas agregar otra.');
  }
});
btnPickFolder.addEventListener('click', e => {
  if (selectedItems.length >= MAX_IMAGES) {
    e.preventDefault();
    showLimitNotice('⚠️ Ya tienes ' + MAX_IMAGES + ' imágenes cargadas. Quita alguna si deseas agregar otra.');
  }
});

dropzone.addEventListener('click', e => {
  if (e.target.closest('label') || e.target.closest('button')) return;
  openFilePicker();
});

soilFile.addEventListener('change', () => {
  const picked = Array.from(soilFile.files || []);
  soilFile.value = '';
  if (picked.length > 0) addFiles(picked);
});

soilFolder.addEventListener('change', () => {
  const picked = Array.from(soilFolder.files || []).filter(f => {
    if (f.type && f.type.startsWith('image/')) return true;
    return /\.(jpe?g|png|webp|bmp|jfif)$/i.test(f.name || '');
  });
  soilFolder.value = '';
  if (picked.length === 0) {
    showLimitNotice('⚠️ No se encontraron imágenes válidas dentro de esa carpeta.');
    return;
  }
  openPickerModal(picked);
});

btnResetPhoto.addEventListener('click', clearSelection);

function prepareImageForUpload(file) {
  return new Promise(resolve => {
    const img = new Image();
    const tmpUrl = URL.createObjectURL(file);
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 512;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          URL.revokeObjectURL(tmpUrl);
          resolve(file);
          return;
        }
        ctx.drawImage(img, 0, 0, 512, 512);
        canvas.toBlob(blob => {
          URL.revokeObjectURL(tmpUrl);
          if (blob && blob.size > 0) {
            const baseName = file.name.replace(/\.[^.]+$/, '') || 'muestra';
            resolve(new File([blob], baseName + '.jpg', { type: 'image/jpeg' }));
          } else {
            resolve(file);
          }
        }, 'image/jpeg', 0.88);
      } catch (_) {
        URL.revokeObjectURL(tmpUrl);
        resolve(file);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(tmpUrl);
      resolve(file);
    };
    img.src = tmpUrl;
  });
}

function getStatusStyle(status, soilType) {
  if (status === 'monte') {
    return { text: 'text-amber-400', crop: 'text-amber-200', pill: 'bg-amber-950/85 border-amber-500/60 text-amber-200' };
  }
  if (status === 'invalid' || status === 'error') {
    return { text: 'text-red-400', crop: 'text-red-300', pill: 'bg-red-950/85 border-red-500/60 text-red-200' };
  }
  if (soilType === 'Arenoso') {
    return { text: 'text-emerald-400', crop: 'text-amber-200', pill: 'bg-emerald-950/85 border-emerald-500/60 text-emerald-200' };
  }
  if (soilType === 'Arcilloso') {
    return { text: 'text-orange-400', crop: 'text-amber-200', pill: 'bg-orange-950/85 border-orange-500/60 text-orange-200' };
  }
  return { text: 'text-lime-400', crop: 'text-amber-200', pill: 'bg-lime-950/85 border-lime-500/60 text-lime-200' };
}

function getMoistureStyle(level) {
  if (level === 'Seco') {
    return { text: 'text-amber-400', bar: 'bg-gradient-to-r from-amber-500 to-yellow-400', icon: '🏜️' };
  }
  if (level === 'Húmedo / Saturado') {
    return { text: 'text-blue-400', bar: 'bg-gradient-to-r from-blue-600 to-cyan-400', icon: '🌊' };
  }
  return { text: 'text-sky-400', bar: 'bg-gradient-to-r from-sky-500 to-teal-400', icon: '💧' };
}

function getManagementPlan(soilStatus, soilType, moistureLevel) {
  if (soilStatus === 'monte') {
    return {
      context: 'Terreno con cobertura vegetal',
      steps: [
        { title: 'Desmonte y limpieza', icon: '🪓', text: 'Realizar desmonte selectivo y retiro de maleza superficial evitando remover la capa fértil.' },
        { title: 'Control de rebrotes', icon: '🌱', text: 'Incorporar restos vegetales picados como cobertura orgánica para conservar humedad y evitar erosión.' },
        { title: 'Nuevo muestreo', icon: '📸', text: 'Tomar nuevas fotos directamente sobre tierra descubierta para obtener clasificación y humedad precisas.' },
      ],
    };
  }
  if (soilStatus !== 'valid') return null;

  const matrix = {
    Arenoso: {
      Seco: [
        { title: 'Preparación mínima', icon: '🚜', text: 'Evitar labranza excesiva para no pulverizar el suelo ni acelerar la pérdida de humedad.' },
        { title: 'Manejo hídrico', icon: '💧', text: 'Aplicar riego fraccionado o esperar lluvias iniciales; el suelo arenoso drena rápido y retiene poca agua.' },
        { title: 'Siembra Gran Chaco', icon: '🌾', text: 'Priorizar sorgo granífero o sésamo con cobertura vegetal (mulch) para reducir evaporación.' },
      ],
      'Humedad Óptima': [
        { title: 'Preparación ligera', icon: '🚜', text: 'Labranza mínima o siembra directa aprovechando la buena aireación natural del suelo arenoso.' },
        { title: 'Manejo hídrico', icon: '💧', text: 'Condición ideal de humedad; planificar riegos cortos y frecuentes en etapas de floración.' },
        { title: 'Siembra Gran Chaco', icon: '🌾', text: 'Ventana favorable para sembrar sorgo granífero o sésamo con buena emergencia de plántulas.' },
      ],
      'Húmedo / Saturado': [
        { title: 'Oreo breve', icon: '☀️', text: 'Esperar 12–24 horas de escurrimiento natural; el suelo arenoso drena con rapidez sin compactarse en exceso.' },
        { title: 'Manejo hídrico', icon: '🌊', text: 'Controlar lavado de nutrientes (lixiviación) y fraccionar la fertilización nitrogenada.' },
        { title: 'Siembra Gran Chaco', icon: '🌾', text: 'Una vez oreado, sembrar sorgo o sésamo cuidando profundidad uniforme de semilla.' },
      ],
    },
    Arcilloso: {
      Seco: [
        { title: 'Subsolado / rotura', icon: '🚜', text: 'Suelo arcilloso seco puede formar terrones duros; esperar humedad moderada antes de laborear.' },
        { title: 'Manejo hídrico', icon: '💧', text: 'Realizar riego previo de asiento o esperar lluvia para facilitar infiltración homogénea.' },
        { title: 'Siembra Gran Chaco', icon: '🌽', text: 'Apto para maíz o soya tras humedecer la cama de siembra para evitar fallas de germinación.' },
      ],
      'Humedad Óptima': [
        { title: 'Labranza oportuna', icon: '🚜', text: 'Momento ideal de friabilidad (capacidad de campo) para preparar cama de siembra sin terrones ni barro.' },
        { title: 'Manejo hídrico', icon: '💧', text: 'Excelente retención hídrica; aprovechar la humedad almacenada y vigilar drenaje en zonas bajas.' },
        { title: 'Siembra Gran Chaco', icon: '🌽', text: 'Condición óptima para siembra directa de maíz o soya con alta uniformidad de emergencia.' },
      ],
      'Húmedo / Saturado': [
        { title: 'Evitar compactación', icon: '⛔', text: 'No ingresar maquinaria pesada en arcilla saturada: genera piso de arado y sellado superficial.' },
        { title: 'Oreo y drenaje', icon: '🌊', text: 'Esperar 2–3 días de oreo y habilitar surcos de escurrimiento en sectores con encharcamiento.' },
        { title: 'Siembra Gran Chaco', icon: '🌽', text: 'Sembrar maíz o soya solo cuando la tierra no se adhiera a los implementos para evitar pudrición.' },
      ],
    },
    Limoso: {
      Seco: [
        { title: 'Cobertura superficial', icon: '🚜', text: 'Proteger con rastrojo para evitar formación de costra superficial y erosión eólica.' },
        { title: 'Manejo hídrico', icon: '💧', text: 'Aplicar riego suave o esperar lluvia moderada para reponer humedad en los primeros 15 cm.' },
        { title: 'Siembra Gran Chaco', icon: '🫘', text: 'Preparar siembra de soya o fréjol asegurando contacto firme semilla–suelo húmedo.' },
      ],
      'Humedad Óptima': [
        { title: 'Preparación balanceada', icon: '🚜', text: 'Textura equilibrada y fácil de trabajar; mantener residuos vegetales para preservar estructura.' },
        { title: 'Manejo hídrico', icon: '💧', text: 'Buena retención de agua disponible para raíces; monitoreo estándar durante llenado de grano.' },
        { title: 'Siembra Gran Chaco', icon: '🫘', text: 'Excelente condición para sembrar soya o fréjol con alto potencial de rendimiento.' },
      ],
      'Húmedo / Saturado': [
        { title: 'Prevención de costra', icon: '☀️', text: 'Esperar oreo antes de labrar; el limo húmedo al secarse rápido puede encostrar la superficie.' },
        { title: 'Manejo hídrico', icon: '🌊', text: 'Facilitar drenaje superficial para evitar asfixia radicular en leguminosas.' },
        { title: 'Siembra Gran Chaco', icon: '🫘', text: 'Diferir siembra de soya o fréjol 1–2 días hasta recuperar textura suelta y aireada.' },
      ],
    },
  };

  const bySoil = matrix[soilType] || matrix.Limoso;
  const steps = bySoil[moistureLevel] || bySoil['Humedad Óptima'];
  return { context: soilType + (moistureLevel ? (' · ' + moistureLevel) : ''), steps };
}

// ---------- Historial local ----------
function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

function persistHistory(items) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, MAX_HISTORY_ITEMS)));
  } catch (_) {}
}

function saveAnalysisToHistory(data, parcelName, timestamp) {
  const summary = data.summary || {};
  const results = Array.isArray(data.results) ? data.results : [];
  const total = Number(data.total_images || results.length || 1);
  const isBatch = total > 1;
  const primary = isBatch ? {
    soil_status: summary.dominant_status,
    soil_type: summary.dominant_soil_type,
    recommended_crop: summary.recommended_crop,
    moisture_index: summary.avg_moisture_index,
    moisture_level: summary.dominant_moisture_level,
  } : (results[0] || {});

  const entry = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    parcelName: parcelName || 'Parcela sin nombre',
    timestamp,
    totalImages: total,
    soilStatus: primary.soil_status || 'invalid',
    soilType: primary.soil_type || '—',
    crop: primary.recommended_crop || '—',
    moistureIndex: primary.moisture_index ?? null,
    moistureLevel: primary.moisture_level || null,
    responseMs: Number(data.response_time_ms ?? 0),
  };

  persistHistory([entry, ...loadHistory()].slice(0, MAX_HISTORY_ITEMS));
  renderHistory();
}

function renderHistory() {
  const items = loadHistory();
  if (!items.length) {
    historySection.classList.add('hidden');
    historyList.innerHTML = '';
    return;
  }

  historySection.classList.remove('hidden');
  historyList.innerHTML = items.map(item => {
    const st = getStatusStyle(item.soilStatus, item.soilType);
    const moistHtml = (item.soilStatus === 'valid' && item.moistureIndex !== null && item.moistureIndex !== undefined)
      ? '<span class="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/25 text-sky-300">💧 ' + escapeHtml(item.moistureLevel) + ' (' + Number(item.moistureIndex).toFixed(0) + '%)</span>'
      : '';
    return (
      '<div class="metric-tile rounded-2xl px-4 py-3 border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">' +
      '<div class="min-w-0">' +
      '<div class="flex flex-wrap items-center gap-2">' +
      '<span class="font-semibold text-sm text-white truncate max-w-[220px]">' + escapeHtml(item.parcelName) + '</span>' +
      '<span class="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-slate-400">' + item.totalImages + ' foto(s)</span>' +
      '<span class="text-[11px] font-bold px-2.5 py-0.5 rounded-full border ' + st.pill + '">' + escapeHtml(item.soilType) + '</span>' +
      moistHtml +
      '</div>' +
      '<p class="text-xs text-slate-400 mt-1 truncate">' + escapeHtml(item.crop) + ' · <span class="font-mono text-[11px] text-slate-500">' + escapeHtml(item.timestamp) + ' · ' + Number(item.responseMs).toFixed(0) + ' ms</span></p>' +
      '</div>' +
      '<button type="button" data-del-history="' + item.id + '" title="Eliminar del historial" ' +
      'class="self-end sm:self-center text-xs px-2.5 py-1 rounded-lg bg-white/5 hover:bg-red-500/20 text-slate-400 hover:text-red-300 border border-white/10 transition shrink-0">✕</button>' +
      '</div>'
    );
  }).join('');
}

historyList.addEventListener('click', e => {
  const btn = e.target.closest('[data-del-history]');
  if (!btn) return;
  persistHistory(loadHistory().filter(item => item.id !== btn.dataset.delHistory));
  renderHistory();
});

btnClearHistory.addEventListener('click', () => {
  persistHistory([]);
  renderHistory();
});

renderHistory();

// ---------- Reporte PDF / Imprimible ----------
function openPrintableReport() {
  if (!lastAnalysisContext) {
    showFarmerError('Primero realiza un análisis para generar el reporte técnico.');
    return;
  }
  const { data, parcelName, timestamp } = lastAnalysisContext;
  const summary = data.summary || {};
  const results = Array.isArray(data.results) ? data.results : [];
  const total = Number(data.total_images || results.length || 1);
  const isBatch = total > 1;
  const primary = isBatch ? {
    soil_status: summary.dominant_status,
    soil_type: summary.dominant_soil_type,
    recommended_crop: summary.recommended_crop,
    roughness_index: summary.avg_roughness_index,
    moisture_index: summary.avg_moisture_index,
    moisture_level: summary.dominant_moisture_level,
  } : (results[0] || {});

  const plan = getManagementPlan(primary.soil_status, primary.soil_type, primary.moisture_level);
  const execLabel = data.execution_mode === 'cluster_mpi_openmp'
    ? ('Clúster OpenMPI + OpenMP (' + (data.cluster_nodes || 3) + ' nodos, ' + (data.omp_threads || 4) + ' hilos)')
    : ('Procesamiento Paralelo Serverless (' + (data.workers_used || 1) + ' hilos)');

  const moistureSummaryText = (primary.soil_status === 'valid' && primary.moisture_index !== null && primary.moisture_index !== undefined)
    ? (primary.moisture_level + ' (' + Number(primary.moisture_index).toFixed(1) + '%)')
    : 'No aplica';
  const roughnessSummaryText = (primary.soil_status !== 'invalid' && primary.soil_status !== 'error' && primary.roughness_index !== null && primary.roughness_index !== undefined)
    ? Number(primary.roughness_index).toFixed(4)
    : 'No aplica';

  const rowsHtml = results.map((item, idx) => {
    const mTxt = (item.soil_status === 'valid' && item.moisture_index !== null && item.moisture_index !== undefined)
      ? (escapeHtml(item.moisture_level) + ' (' + Number(item.moisture_index).toFixed(0) + '%)')
      : 'No aplica';
    const rTxt = (item.soil_status !== 'invalid' && item.soil_status !== 'error' && item.roughness_index !== null && item.roughness_index !== undefined)
      ? Number(item.roughness_index).toFixed(4)
      : 'No aplica';
    return (
      '<tr>' +
      '<td>#' + (idx + 1) + '</td>' +
      '<td>' + escapeHtml(item.filename) + '</td>' +
      '<td><strong>' + escapeHtml(item.soil_type) + '</strong></td>' +
      '<td>' + mTxt + '</td>' +
      '<td>' + rTxt + '</td>' +
      '<td>' + escapeHtml(item.recommended_crop) + '</td>' +
      '</tr>'
    );
  }).join('');

  const planHtml = plan
    ? '<div class="section"><h3>Plan de Manejo Recomendado (' + escapeHtml(plan.context) + ')</h3><div class="plan-grid">' +
      plan.steps.map(s => '<div class="plan-card"><strong>' + s.icon + ' ' + escapeHtml(s.title) + '</strong><p>' + escapeHtml(s.text) + '</p></div>').join('') +
      '</div></div>'
    : '';

  const reportHtml =
    '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8" />' +
    '<title>Reporte EDAFix — ' + escapeHtml(parcelName || 'Parcela') + '</title>' +
    '<style>' +
    'body{font-family:Inter,system-ui,sans-serif;color:#0f172a;margin:0;padding:28px;background:#fff;line-height:1.45;}' +
    '.header{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #10b981;padding-bottom:14px;margin-bottom:20px;}' +
    '.brand h1{margin:0;font-size:22px;color:#065f46;} .brand p{margin:3px 0 0;font-size:12px;color:#475569;}' +
    '.meta{text-align:right;font-size:12px;color:#334155;}' +
    '.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px;}' +
    '.kpi{border:1px solid #cbd5e1;border-radius:10px;padding:12px;background:#f8fafc;}' +
    '.kpi label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#64748b;margin-bottom:4px;}' +
    '.kpi .val{font-size:16px;font-weight:700;color:#0f172a;}' +
    '.section{margin-top:18px;} .section h3{font-size:14px;margin:0 0 10px;color:#065f46;border-left:4px solid #10b981;padding-left:8px;}' +
    '.plan-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}' +
    '.plan-card{border:1px solid #e2e8f0;border-radius:8px;padding:10px;background:#f8fafc;font-size:12px;}' +
    '.plan-card p{margin:5px 0 0;color:#334155;}' +
    'table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px;}' +
    'th,td{border:1px solid #cbd5e1;padding:8px;text-align:left;vertical-align:top;}' +
    'th{background:#f1f5f9;font-size:11px;text-transform:uppercase;color:#334155;}' +
    '.note{margin-top:16px;font-size:11px;color:#475569;background:#f8fafc;border:1px solid #e2e8f0;padding:10px;border-radius:8px;}' +
    '.actions{margin-bottom:16px;text-align:right;} .btn{background:#059669;color:#fff;border:none;padding:9px 16px;border-radius:8px;font-weight:600;cursor:pointer;}' +
    '@media print{.actions{display:none;} body{padding:0;}}' +
    '</style></head><body>' +
    '<div class="actions"><button class="btn" onclick="window.print()">🖨️ Imprimir / Guardar como PDF</button></div>' +
    '<div class="header">' +
    '<div class="brand"><h1>🌱 EDAFix — Informe Técnico Edafológico</h1><p>Sistema Híbrido de Visión Artificial Distribuida · Región del Gran Chaco (UAJMS - TEL420)</p></div>' +
    '<div class="meta"><strong>Parcela:</strong> ' + escapeHtml(parcelName || 'Sin especificar') + '<br/><strong>Fecha:</strong> ' + escapeHtml(timestamp) + '<br/><strong>Muestras:</strong> ' + total + ' (' + (summary.valid_soil_count || 0) + ' válidas)</div>' +
    '</div>' +
    '<div class="kpis">' +
    '<div class="kpi"><label>' + (isBatch ? 'Suelo predominante' : 'Tipo de suelo') + '</label><div class="val">' + escapeHtml(primary.soil_type || '—') + '</div></div>' +
    '<div class="kpi"><label>Cultivo recomendado</label><div class="val">' + escapeHtml(primary.recommended_crop || '—') + '</div></div>' +
    '<div class="kpi"><label>Humedad superficial (est.)</label><div class="val">' + escapeHtml(moistureSummaryText) + '</div></div>' +
    '<div class="kpi"><label>Rugosidad Sobel</label><div class="val">' + escapeHtml(roughnessSummaryText) + '</div></div>' +
    '</div>' +
    planHtml +
    '<div class="section"><h3>Detalle de Muestras Analizadas</h3>' +
    '<table><thead><tr><th>#</th><th>Archivo</th><th>Clasificación</th><th>Humedad (est.)</th><th>Rugosidad</th><th>Recomendación</th></tr></thead><tbody>' +
    rowsHtml +
    '</tbody></table></div>' +
    '<div class="note"><strong>Motor de ejecución:</strong> ' + escapeHtml(execLabel) + ' · Tiempo total: ' + Number(data.response_time_ms ?? 0).toFixed(2) + ' ms.<br/>' +
    '<strong>Nota técnica:</strong> La humedad edáfica se estima ópticamente a partir de la reflectancia/luminancia superficial del suelo en imágenes RGB; condiciones extremas de sombra o reflejo solar pueden influir en el valor y no reemplaza un ensayo gravimétrico de laboratorio.</div>' +
    '</body></html>';

  const win = window.open('', '_blank', 'width=960,height=780');
  if (!win) {
    showFarmerError('El navegador bloqueó la ventana emergente del reporte. Permite ventanas emergentes para descargar el PDF.');
    return;
  }
  win.document.open();
  win.document.write(reportHtml);
  win.document.close();
  win.focus();
}

btnDownloadReport.addEventListener('click', openPrintableReport);

function renderAnalysisResponse(data, snapshotItems) {
  const total = Number(data.total_images || 0);
  const summary = data.summary || {};
  const results = Array.isArray(data.results) ? data.results : [];
  const isBatch = total > 1;

  resultFarmer.classList.remove('hidden');

  document.getElementById('resultHeading').textContent = isBatch
    ? 'Diagnóstico Consolidado de la Parcela (' + total + ' imágenes)'
    : 'Resultado del Análisis';

  const modeBadge = document.getElementById('executionModeBadge');
  const parallelDetail = document.getElementById('parallelMetaDetail');
  if (data.execution_mode === 'cluster_mpi_openmp') {
    modeBadge.textContent = '⚡ Clúster MPI + OpenMP (' + (data.cluster_nodes || 3) + ' nodos · ' + (data.omp_threads || 4) + ' hilos)';
    const dist = data.node_distribution || {};
    const distText = Object.entries(dist).map(([k, v]) => k + ': ' + v).join(' · ');
    parallelDetail.textContent = 'Reparto en clúster (' + distText + ') · Tiempo MPI: ' + Number(data.cluster_time_ms ?? 0).toFixed(2) + ' ms';
  } else {
    modeBadge.textContent = '☁️ Paralelo Serverless (' + (data.workers_used || 1) + ' hilos)';
    parallelDetail.textContent = isBatch
      ? 'Lote de ' + total + ' muestras procesado concurrentemente (optimizado para Vercel)'
      : 'Muestra procesada en backend serverless';
  }

  document.getElementById('responseTime').textContent = Number(data.response_time_ms ?? 0).toFixed(2) + ' ms';

  const primary = isBatch ? {
    soil_status: summary.dominant_status,
    is_valid_soil: summary.dominant_status === 'valid',
    soil_type: summary.dominant_soil_type,
    recommended_crop: summary.recommended_crop,
    roughness_index: summary.avg_roughness_index,
    moisture_index: summary.avg_moisture_index,
    moisture_level: summary.dominant_moisture_level,
    moisture_advice: summary.moisture_advice,
    lighting_warning: summary.lighting_warning,
  } : (results[0] || {});

  document.getElementById('soilTypeLabel').textContent = isBatch ? 'Suelo predominante' : 'Tipo de suelo';
  document.getElementById('moistureLabel').textContent = isBatch ? 'Humedad promedio (est.)' : 'Humedad superficial (est.)';
  document.getElementById('roughnessLabel').textContent = isBatch ? 'Rugosidad promedio (Sobel)' : 'Índice de rugosidad (Sobel)';

  const badge = document.getElementById('soilType');
  const cropEl = document.getElementById('recommendedCrop');
  const roughnessEl = document.getElementById('roughness');
  const dominanceMeta = document.getElementById('soilDominanceMeta');
  const moistureEl = document.getElementById('moistureLevel');
  const moistureBarWrap = document.getElementById('moistureBarWrap');
  const moistureBar = document.getElementById('moistureBar');
  const moistureAdviceEl = document.getElementById('moistureAdvice');
  const moistureNote = document.getElementById('moistureOpticalNote');

  const style = getStatusStyle(primary.soil_status, primary.soil_type);
  badge.textContent = primary.soil_type || '—';
  badge.className = 'font-display text-2xl font-extrabold leading-tight ' + style.text;
  cropEl.textContent = primary.recommended_crop || '—';
  cropEl.className = 'text-base sm:text-lg font-bold leading-snug ' + style.crop;

  if (isBatch && summary.dominant_status === 'valid') {
    dominanceMeta.textContent = summary.dominant_count + ' de ' + summary.valid_soil_count + ' válidas (' + summary.dominant_percentage + '%)';
    dominanceMeta.classList.remove('hidden');
  } else {
    dominanceMeta.classList.add('hidden');
  }

  if (primary.soil_status === 'valid' && primary.moisture_index !== null && primary.moisture_index !== undefined) {
    const mStyle = getMoistureStyle(primary.moisture_level);
    const pct = Math.max(0, Math.min(100, Number(primary.moisture_index)));
    moistureEl.textContent = mStyle.icon + ' ' + primary.moisture_level + ' (' + pct.toFixed(0) + '%)';
    moistureEl.className = 'font-display text-xl font-extrabold leading-tight ' + mStyle.text;
    moistureBar.style.width = pct + '%';
    moistureBar.className = 'h-2 rounded-full transition-all duration-500 ' + mStyle.bar;
    moistureAdviceEl.textContent = primary.moisture_advice || '';
    moistureBarWrap.classList.remove('hidden');
    moistureNote.textContent = primary.lighting_warning
      ? '⚠️ Se detectaron reflejos/brillo parcial en la escena: la estimación óptica de humedad superficial puede variar según la iluminación.'
      : 'ℹ️ Estimación óptica sobre la capa superficial del suelo (sombras intensas o reflejos solares pueden influir en el valor).';
    moistureNote.className = primary.lighting_warning
      ? 'mt-3.5 text-[11px] text-amber-300'
      : 'mt-3.5 text-[11px] text-slate-400';
  } else if (primary.soil_status === 'monte') {
    moistureEl.textContent = 'No aplica (monte)';
    moistureEl.className = 'text-base font-semibold text-slate-500 mt-1';
    moistureBarWrap.classList.add('hidden');
    moistureNote.classList.add('hidden');
  } else {
    moistureEl.textContent = 'No aplica (no es suelo)';
    moistureEl.className = 'text-base font-semibold text-slate-500 mt-1';
    moistureBarWrap.classList.add('hidden');
    moistureNote.classList.add('hidden');
  }

  if (primary.soil_status === 'invalid' || primary.soil_status === 'error' || primary.roughness_index === null || primary.roughness_index === undefined) {
    roughnessEl.textContent = 'No aplica';
    roughnessEl.className = 'text-base font-semibold text-slate-500 mt-1';
  } else {
    roughnessEl.textContent = Number(primary.roughness_index).toFixed(4);
    roughnessEl.className = 'font-mono text-2xl font-bold text-amber-400';
  }

  const invalidAlert = document.getElementById('invalidSoilAlert');
  const monteAlert = document.getElementById('monteSoilAlert');
  const mixedBatchNote = document.getElementById('mixedBatchNote');
  invalidAlert.classList.add('hidden');
  monteAlert.classList.add('hidden');
  mixedBatchNote.classList.add('hidden');

  if (primary.soil_status === 'monte') {
    monteAlert.classList.remove('hidden');
  } else if (primary.soil_status === 'invalid' || primary.soil_status === 'error') {
    invalidAlert.classList.remove('hidden');
  } else if (isBatch && ((summary.monte_count || 0) > 0 || (summary.invalid_count || 0) > 0 || (summary.error_count || 0) > 0)) {
    const parts = [];
    if (summary.monte_count > 0) parts.push(summary.monte_count + ' con monte/maleza');
    if (summary.invalid_count > 0) parts.push(summary.invalid_count + ' no apta(s)');
    if (summary.error_count > 0) parts.push(summary.error_count + ' con error de lectura');
    mixedBatchNote.innerHTML = 'ℹ️ <strong>Nota de la parcela:</strong> El diagnóstico principal y la humedad promedio se calcularon solo con las <strong>' + summary.valid_soil_count + ' muestra(s) de suelo válido</strong>. También se detectaron ' + parts.join(' y ') + '.';
    mixedBatchNote.classList.remove('hidden');
  }

  const plan = getManagementPlan(primary.soil_status, primary.soil_type, primary.moisture_level);
  if (plan) {
    managementPlanContext.textContent = plan.context;
    managementPlanGrid.innerHTML = plan.steps.map(step =>
      '<div class="rounded-xl p-3.5 bg-slate-950/70 border border-white/10">' +
      '<p class="text-xs font-bold text-emerald-300 mb-1">' + step.icon + ' ' + escapeHtml(step.title) + '</p>' +
      '<p class="text-xs text-slate-300 leading-relaxed">' + escapeHtml(step.text) + '</p>' +
      '</div>'
    ).join('');
    managementPlanBox.classList.remove('hidden');
  } else {
    managementPlanBox.classList.add('hidden');
    managementPlanGrid.innerHTML = '';
  }

  const distBox = document.getElementById('batchDistributionBox');
  const distPills = document.getElementById('batchDistributionPills');
  const stackedBar = document.getElementById('batchStackedBar');
  const validRatioEl = document.getElementById('batchValidRatio');
  const detailsSection = document.getElementById('batchDetailsSection');
  const detailsGrid = document.getElementById('batchResultsGrid');
  const detailsCount = document.getElementById('batchDetailsCount');

  if (!isBatch) {
    distBox.classList.add('hidden');
    detailsSection.classList.add('hidden');
    resultFarmer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    return;
  }

  const counts = summary.counts_by_soil || {};
  const segments = [
    { label: 'Arenoso', count: counts.Arenoso || 0, cls: 'bg-emerald-500/15 border-emerald-500/35 text-emerald-200', bar: 'bg-emerald-500' },
    { label: 'Arcilloso', count: counts.Arcilloso || 0, cls: 'bg-orange-500/15 border-orange-500/35 text-orange-200', bar: 'bg-orange-500' },
    { label: 'Limoso', count: counts.Limoso || 0, cls: 'bg-lime-500/15 border-lime-500/35 text-lime-200', bar: 'bg-lime-500' },
    { label: 'Monte / Vegetación', count: summary.monte_count || 0, cls: 'bg-amber-500/15 border-amber-500/35 text-amber-200', bar: 'bg-amber-500' },
    { label: 'No apto', count: (summary.invalid_count || 0) + (summary.error_count || 0), cls: 'bg-red-500/15 border-red-500/35 text-red-200', bar: 'bg-red-500' },
  ].filter(p => p.count > 0);

  validRatioEl.textContent = (summary.valid_soil_count || 0) + ' / ' + total + ' válidas';
  stackedBar.innerHTML = segments.map(s => {
    const pct = (s.count / total) * 100;
    return '<div class="h-full ' + s.bar + '" style="width: ' + pct.toFixed(1) + '%" title="' + s.label + ': ' + s.count + '"></div>';
  }).join('');

  distPills.innerHTML = segments.map(p =>
    '<span class="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full border ' + p.cls + '">' +
    '<span class="w-2 h-2 rounded-full ' + p.bar + '"></span>' +
    p.label + ': <strong class="font-mono">' + p.count + '</strong></span>'
  ).join('');
  distBox.classList.remove('hidden');

  detailsCount.textContent = results.length + ' muestra(s)';
  detailsGrid.innerHTML = results.map((item, idx) => {
    const snap = snapshotItems[item.index] || snapshotItems[idx];
    const thumbUrl = snap ? snap.url : '';
    const st = getStatusStyle(item.soil_status, item.soil_type);
    const showRoughness = item.soil_status !== 'invalid' && item.soil_status !== 'error' && item.roughness_index !== null && item.roughness_index !== undefined;
    const roughText = showRoughness ? Number(item.roughness_index).toFixed(4) : 'No aplica';
    const showMoisture = item.soil_status === 'valid' && item.moisture_index !== null && item.moisture_index !== undefined;
    const mSt = showMoisture ? getMoistureStyle(item.moisture_level) : null;
    const moistText = showMoisture
      ? (mSt.icon + ' ' + escapeHtml(item.moisture_level) + ' (' + Number(item.moisture_index).toFixed(0) + '%)')
      : 'No aplica';

    return (
      '<article class="metric-tile border border-white/10 hover:border-white/20 rounded-2xl overflow-hidden flex flex-col transition group">' +
      '<div class="relative h-40 bg-slate-950 overflow-hidden">' +
      (thumbUrl ? '<img src="' + thumbUrl + '" alt="Muestra ' + (idx + 1) + '" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />' : '') +
      '<div class="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-transparent to-slate-950/30 pointer-events-none"></div>' +
      '<span class="absolute top-2.5 left-2.5 text-[10px] font-mono font-bold px-2 py-0.5 rounded-md bg-slate-950/80 text-slate-200 border border-white/15 backdrop-blur">#' + (idx + 1) + '</span>' +
      '<span class="absolute bottom-2.5 right-2.5 text-[11px] font-bold px-2.5 py-0.5 rounded-full border backdrop-blur ' + st.pill + '">' + escapeHtml(item.soil_type) + '</span>' +
      '</div>' +
      '<div class="p-4 flex-1 flex flex-col justify-between gap-3">' +
      '<div>' +
      '<p class="text-[11px] font-mono text-slate-400 truncate mb-2" title="' + escapeHtml(item.filename) + '">' + escapeHtml(item.filename) + '</p>' +
      '<p class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Cultivo recomendado</p>' +
      '<p class="text-sm font-semibold ' + st.crop + ' mt-0.5 leading-snug">' + escapeHtml(item.recommended_crop) + '</p>' +
      '</div>' +
      '<div class="pt-3 border-t border-white/10 space-y-2 text-xs">' +
      '<div class="flex items-center justify-between gap-2">' +
      '<span class="text-slate-400">Humedad (est.)</span>' +
      '<span class="font-semibold text-right ' + (showMoisture ? mSt.text : 'text-slate-500') + '">' + moistText + '</span>' +
      '</div>' +
      '<div class="flex items-center justify-between gap-2">' +
      '<span class="text-slate-400">Rugosidad (Sobel)</span>' +
      '<span class="font-mono font-bold ' + (showRoughness ? 'text-amber-400' : 'text-slate-500') + '">' + roughText + '</span>' +
      '</div>' +
      '</div>' +
      '</div>' +
      '</article>'
    );
  }).join('');
  detailsSection.classList.remove('hidden');
  resultFarmer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

btnAnalyze.addEventListener('click', async () => {
  showFarmerError('');
  if (selectedItems.length === 0) {
    showFarmerError('Selecciona o arrastra entre 1 y 10 imágenes de suelo primero.');
    return;
  }

  const snapshotItems = selectedItems.slice();
  const count = snapshotItems.length;
  btnAnalyze.disabled = true;
  btnAnalyzeIcon.innerHTML = ICON_SPINNER;
  btnAnalyzeLabel.textContent = count === 1
    ? 'Optimizando y analizando imagen...'
    : 'Analizando ' + count + ' imágenes en paralelo...';

  try {
    const preparedFiles = await Promise.all(snapshotItems.map(item => prepareImageForUpload(item.file)));
    const form = new FormData();
    preparedFiles.forEach((file, idx) => {
      form.append('files', file, snapshotItems[idx].file.name || file.name);
    });

    const res = await fetch(API_BASE + '/api/analyze-batch', { method: 'POST', body: form });
    let data;
    try {
      data = await res.json();
    } catch (_) {
      throw new Error('Respuesta inválida del servidor (HTTP ' + res.status + ')');
    }
    if (!res.ok) {
      throw new Error(data.detail || ('Error HTTP ' + res.status));
    }

    const parcelName = parcelNameInput ? parcelNameInput.value.trim() : '';
    const timestamp = new Date().toLocaleString('es-BO', { dateStyle: 'short', timeStyle: 'short' });
    lastAnalysisContext = { data, parcelName, timestamp };
    renderAnalysisResponse(data, snapshotItems);
    saveAnalysisToHistory(data, parcelName, timestamp);
  } catch (err) {
    showFarmerError('Error conectando con el backend: ' + (err.message || 'desconocido'));
  } finally {
    btnAnalyze.disabled = selectedItems.length === 0;
    btnAnalyzeIcon.innerHTML = ICON_BOLT;
    btnAnalyzeLabel.textContent = selectedItems.length <= 1
      ? 'Analizar ' + (selectedItems.length === 1 ? '1 Imagen' : 'Suelo') + ' en Paralelo'
      : 'Analizar ' + selectedItems.length + ' Imágenes en Paralelo';
  }
});

async function trainCurrentSample(label) {
  const msgEl = document.getElementById('trainStatusMsg');
  try {
    const res = await fetch(API_BASE + '/api/train-sample', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al guardar muestra');
    if (msgEl) {
      msgEl.textContent = '✅ Muestra guardada en data/dataset_suelos/' + label + ' (' + data.file + '). Volviendo a analizar...';
      msgEl.classList.remove('hidden');
    }
    btnAnalyze.click();
  } catch (err) {
    showFarmerError('Error guardando en el dataset: ' + (err.message || 'desconocido'));
  }
}

// ---------- Tab 2: Benchmark ----------
const btnBenchmark = document.getElementById('btnBenchmark');
const btnBenchmarkLabel = document.getElementById('btnBenchmarkLabel');
const benchmarkResults = document.getElementById('benchmarkResults');
const benchmarkError = document.getElementById('benchmarkError');
const timeSavedBadge = document.getElementById('timeSavedBadge');

btnBenchmark.addEventListener('click', async () => {
  btnBenchmark.disabled = true;
  btnBenchmarkLabel.textContent = 'Ejecutando benchmark en clúster (3 nodos)...';
  benchmarkError.classList.add('hidden');
  benchmarkResults.classList.add('hidden');

  try {
    const res = await fetch(API_BASE + '/api/run-cluster', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        num_images: Number(document.getElementById('numImages').value),
        omp_threads: Number(document.getElementById('ompThreads').value),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || ('Error HTTP ' + res.status));

    const T1 = Number(data.T1);
    const Tp = Number(data.Tp);
    const Speedup = Number(data.Speedup);
    const Eficiencia = Number(data.Eficiencia);

    document.getElementById('kpiT1').textContent = T1.toFixed(6) + ' s';
    document.getElementById('kpiTp').textContent = Tp.toFixed(6) + ' s';
    document.getElementById('kpiSpeedup').textContent = '×' + Speedup.toFixed(2);
    document.getElementById('kpiEff').textContent = (Eficiencia * 100).toFixed(2) + ' %';

    const maxT = Math.max(T1, Tp) || 1;
    document.getElementById('barT1').style.width = (T1 / maxT * 100) + '%';
    document.getElementById('barT1Label').textContent = T1.toFixed(6) + ' s';
    document.getElementById('barTp').style.width = (Tp / maxT * 100) + '%';
    document.getElementById('barTpLabel').textContent = Tp.toFixed(6) + ' s';

    if (T1 > 0 && Tp < T1) {
      const savedPct = ((1 - Tp / T1) * 100).toFixed(1);
      timeSavedBadge.textContent = '-' + savedPct + '% tiempo';
      timeSavedBadge.classList.remove('hidden');
    } else {
      timeSavedBadge.classList.add('hidden');
    }

    benchmarkResults.classList.remove('hidden');
  } catch (err) {
    benchmarkError.textContent = '❌ Error ejecutando el benchmark: ' + (err.message || 'desconocido');
    benchmarkError.classList.remove('hidden');
  } finally {
    btnBenchmark.disabled = false;
    btnBenchmarkLabel.textContent = 'Ejecutar Benchmark en Vivo (3 Nodos)';
  }
});

// ---------- Barrido Completo + Gráficos SVG + CSV ----------
const btnSweep = document.getElementById('btnSweep');
const btnSweepLabel = document.getElementById('btnSweepLabel');
const sweepResults = document.getElementById('sweepResults');
const sweepHeading = document.getElementById('sweepHeading');
const speedupChartWrap = document.getElementById('speedupChartWrap');
const efficiencyChartWrap = document.getElementById('efficiencyChartWrap');
const sweepTableBody = document.getElementById('sweepTableBody');
const btnExportCsv = document.getElementById('btnExportCsv');

let lastSweepRows = [];

function renderSpeedupChart(rows) {
  const W = 440, H = 220;
  const pad = { top: 22, right: 24, bottom: 36, left: 42 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const maxP = Math.max(...rows.map(r => r.total_threads), 12);
  const maxY = Math.max(maxP, ...rows.map(r => r.Speedup), 4);
  const xOf = p => pad.left + ((p - 1) / Math.max(1, maxP - 1)) * plotW;
  const yOf = v => pad.top + plotH - (v / maxY) * plotH;

  const yTicks = [0, 3, 6, 9, 12].filter(t => t <= maxY + 0.5);
  const gridSvg = yTicks.map(t => {
    const y = yOf(t).toFixed(1);
    return (
      '<line x1="' + pad.left + '" y1="' + y + '" x2="' + (W - pad.right) + '" y2="' + y + '" stroke="rgba(148,163,184,0.14)" stroke-width="1" />' +
      '<text x="' + (pad.left - 8) + '" y="' + (Number(y) + 3.5) + '" text-anchor="end" fill="#94a3b8" font-size="10" font-family="JetBrains Mono, monospace">' + t + 'x</text>'
    );
  }).join('');

  const idealLine =
    '<line x1="' + xOf(1).toFixed(1) + '" y1="' + yOf(1).toFixed(1) + '" x2="' + xOf(maxP).toFixed(1) + '" y2="' + yOf(maxP).toFixed(1) + '" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4" />';

  const pts = [{ p: 1, s: 1 }, ...rows.map(r => ({ p: r.total_threads, s: r.Speedup }))];
  const polyPts = pts.map(pt => xOf(pt.p).toFixed(1) + ',' + yOf(pt.s).toFixed(1)).join(' ');
  const areaPts = polyPts + ' ' + xOf(pts[pts.length - 1].p).toFixed(1) + ',' + yOf(0).toFixed(1) + ' ' + xOf(1).toFixed(1) + ',' + yOf(0).toFixed(1);

  const dotsSvg = pts.map((pt, i) => {
    const cx = xOf(pt.p).toFixed(1);
    const cy = yOf(pt.s).toFixed(1);
    const label = i === 0 ? '1.00×' : (pt.s.toFixed(2) + '×');
    return (
      '<circle cx="' + cx + '" cy="' + cy + '" r="4.5" fill="' + (i === 0 ? '#94a3b8' : '#10b981') + '" stroke="#020617" stroke-width="2" />' +
      '<text x="' + cx + '" y="' + (Number(cy) - 10) + '" text-anchor="middle" fill="' + (i === 0 ? '#cbd5e1' : '#6ee7b7') + '" font-size="10" font-weight="700" font-family="JetBrains Mono, monospace">' + label + '</text>' +
      '<text x="' + cx + '" y="' + (H - 12) + '" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="JetBrains Mono, monospace">P=' + pt.p + '</text>'
    );
  }).join('');

  speedupChartWrap.innerHTML =
    '<svg viewBox="0 0 ' + W + ' ' + H + '" class="w-full h-auto">' +
    '<defs><linearGradient id="spGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#10b981" stop-opacity="0.32"/><stop offset="100%" stop-color="#10b981" stop-opacity="0.01"/></linearGradient></defs>' +
    gridSvg + idealLine +
    '<polygon points="' + areaPts + '" fill="url(#spGrad)" />' +
    '<polyline points="' + polyPts + '" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />' +
    dotsSvg +
    '</svg>';
}

function renderEfficiencyChart(rows) {
  const W = 440, H = 220;
  const pad = { top: 22, right: 24, bottom: 36, left: 42 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const xOfIdx = i => pad.left + (rows.length === 1 ? plotW / 2 : (i / (rows.length - 1)) * plotW);
  const yOf = pct => pad.top + plotH - (Math.min(100, Math.max(0, pct)) / 100) * plotH;

  const gridSvg = [0, 25, 50, 75, 100].map(t => {
    const y = yOf(t).toFixed(1);
    return (
      '<line x1="' + pad.left + '" y1="' + y + '" x2="' + (W - pad.right) + '" y2="' + y + '" stroke="rgba(148,163,184,0.14)" stroke-width="1" />' +
      '<text x="' + (pad.left - 8) + '" y="' + (Number(y) + 3.5) + '" text-anchor="end" fill="#94a3b8" font-size="10" font-family="JetBrains Mono, monospace">' + t + '%</text>'
    );
  }).join('');

  const pts = rows.map((r, i) => ({ x: xOfIdx(i), y: yOf(r.Eficiencia * 100), pct: r.Eficiencia * 100, p: r.total_threads }));
  const polyPts = pts.map(pt => pt.x.toFixed(1) + ',' + pt.y.toFixed(1)).join(' ');
  const areaPts = polyPts + ' ' + pts[pts.length - 1].x.toFixed(1) + ',' + yOf(0).toFixed(1) + ' ' + pts[0].x.toFixed(1) + ',' + yOf(0).toFixed(1);

  const dotsSvg = pts.map(pt =>
    '<circle cx="' + pt.x.toFixed(1) + '" cy="' + pt.y.toFixed(1) + '" r="5" fill="#38bdf8" stroke="#020617" stroke-width="2" />' +
    '<text x="' + pt.x.toFixed(1) + '" y="' + (pt.y - 10).toFixed(1) + '" text-anchor="middle" fill="#7dd3fc" font-size="10.5" font-weight="700" font-family="JetBrains Mono, monospace">' + pt.pct.toFixed(1) + '%</text>' +
    '<text x="' + pt.x.toFixed(1) + '" y="' + (H - 12) + '" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="JetBrains Mono, monospace">P=' + pt.p + '</text>'
  ).join('');

  efficiencyChartWrap.innerHTML =
    '<svg viewBox="0 0 ' + W + ' ' + H + '" class="w-full h-auto">' +
    '<defs><linearGradient id="efGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#38bdf8" stop-opacity="0.30"/><stop offset="100%" stop-color="#38bdf8" stop-opacity="0.01"/></linearGradient></defs>' +
    gridSvg +
    '<polygon points="' + areaPts + '" fill="url(#efGrad)" />' +
    '<polyline points="' + polyPts + '" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />' +
    dotsSvg +
    '</svg>';
}

btnSweep.addEventListener('click', async () => {
  const numImages = Number(document.getElementById('numImages').value);
  const threadConfigs = [1, 2, 4];
  btnSweep.disabled = true;
  btnBenchmark.disabled = true;
  benchmarkError.classList.add('hidden');
  sweepResults.classList.add('hidden');

  const collected = [];
  try {
    for (let i = 0; i < threadConfigs.length; i++) {
      const omp = threadConfigs[i];
      btnSweepLabel.textContent = 'Ejecutando ' + (i + 1) + '/3 (' + omp + ' hilo' + (omp > 1 ? 's' : '') + ' OMP)...';
      const res = await fetch(API_BASE + '/api/run-cluster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ num_images: numImages, omp_threads: omp }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || ('Error HTTP ' + res.status));
      collected.push({
        num_images: numImages,
        nodes: 3,
        omp_threads: omp,
        total_threads: 3 * omp,
        T1: Number(data.T1),
        Tp: Number(data.Tp),
        Speedup: Number(data.Speedup),
        Eficiencia: Number(data.Eficiencia),
      });
    }

    lastSweepRows = collected;
    sweepHeading.textContent = 'Análisis de Escalabilidad — Lote N = ' + numImages + ' imágenes';
    renderSpeedupChart(collected);
    renderEfficiencyChart(collected);

    sweepTableBody.innerHTML = collected.map(r =>
      '<tr class="hover:bg-white/[0.03] transition">' +
      '<td class="px-4 py-3">' + r.num_images + '</td>' +
      '<td class="px-4 py-3">' + r.nodes + '</td>' +
      '<td class="px-4 py-3">' + r.omp_threads + '</td>' +
      '<td class="px-4 py-3 font-bold text-white">' + r.total_threads + '</td>' +
      '<td class="px-4 py-3 text-amber-300">' + r.T1.toFixed(6) + '</td>' +
      '<td class="px-4 py-3 text-emerald-300">' + r.Tp.toFixed(6) + '</td>' +
      '<td class="px-4 py-3 font-bold text-teal-300">×' + r.Speedup.toFixed(4) + '</td>' +
      '<td class="px-4 py-3 font-bold text-sky-300">' + (r.Eficiencia * 100).toFixed(2) + '%</td>' +
      '</tr>'
    ).join('');

    sweepResults.classList.remove('hidden');
    sweepResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (err) {
    benchmarkError.textContent = '❌ Error ejecutando el barrido completo: ' + (err.message || 'desconocido');
    benchmarkError.classList.remove('hidden');
  } finally {
    btnSweep.disabled = false;
    btnBenchmark.disabled = false;
    btnSweepLabel.textContent = 'Barrido Completo (1, 2 y 4 hilos)';
  }
});

btnExportCsv.addEventListener('click', () => {
  if (!lastSweepRows.length) return;
  const header = 'N_Imagenes,Nodos_MPI,Hilos_OMP,Total_Hilos_P,Tiempo_Secuencial_s,Tiempo_Paralelo_s,Speedup,Eficiencia';
  const lines = lastSweepRows.map(r =>
    [r.num_images, r.nodes, r.omp_threads, r.total_threads, r.T1.toFixed(6), r.Tp.toFixed(6), r.Speedup.toFixed(4), r.Eficiencia.toFixed(4)].join(',')
  );
  const csv = [header, ...lines].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'edafix_benchmark_N' + lastSweepRows[0].num_images + '.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});
