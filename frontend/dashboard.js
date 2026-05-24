/**
 * dashboard.js — Adaptive Field Intelligence Dashboard
 * =====================================================
 */

'use strict';

const BASE_URL = 'http://localhost:8000';

let soilChart = null;

// ── DOM Element References ─────────────────────────────────────────────────────
// These must be defined before any function uses them (after DOMContentLoaded).
// We use lazy getters so they resolve after the DOM is ready.
let cityInput, languageSelect, refreshBtn, loadingOverlay;
let forecastRow, alertCount, alertList, repositionTbody;
let cropResultCard, cropSelect, getRecBtn, ttsBtn, toastContainer;
let areaInput;

function initDOMRefs() {
  cityInput       = document.getElementById('city-input');
  languageSelect  = document.getElementById('language-select');
  refreshBtn      = document.getElementById('refresh-btn');
  loadingOverlay  = document.getElementById('loading-overlay');
  forecastRow     = document.getElementById('forecast-row');
  alertCount      = document.getElementById('alert-count');
  alertList       = document.getElementById('alert-list');
  repositionTbody = document.getElementById('reposition-tbody');
  cropResultCard  = document.getElementById('crop-result');
  cropSelect      = document.getElementById('crop-select');
  getRecBtn       = document.getElementById('get-recommendation-btn');
  ttsBtn          = document.getElementById('tts-btn');
  toastContainer  = document.getElementById('toast-container');
  areaInput       = document.getElementById('area-input');
}

const UI_TRANSLATIONS = {
  "en": {
    "refresh": "↻ Refresh Data",
    "avg_sm": "Avg Soil Moisture",
    "urgency": "Overall Urgency",
    "drip": "Avg Drip Health",
    "repo": "Pending Repositions",
    "irr_status": "Irrigation Zone Status",
    "alerts_title": "Live Intelligence Alerts",
    "forecast_title": "5-Day Forecast & Irrigation Outlook",
    "planner_title": "Crop-Specific Irrigation Planner",
    "savings_title": "Water & Cost Savings Calculator",
    "score_100": "Score / 100",
    "highest_level": "Highest level",
    "zones_action": "Zones needing action",
    "target_crop": "Target Crop",
    "analyze_needs": "Analyze Needs",
    "optimal": "Optimal",
    "water": "Water",
    "savings_pct": "Savings Percentage",
    "traditional": "Traditional",
    "smart": "Smart",
    "cost_saved": "Cost Saved",
    "reposition_title": "Equipment Repositioning Schedule",
    "col_zone": "Zone",
    "col_stage": "Stage",
    "col_priority": "Priority",
    "col_labor": "Labor",
    "col_date": "Date",
    "col_status": "Status"
  },
  "hi": {
    "refresh": "↻ डेटा ताज़ा करें",
    "avg_sm": "औसत मिट्टी की नमी",
    "urgency": "कुल तात्कालिकता",
    "drip": "औसत ड्रिप स्वास्थ्य",
    "repo": "लंबित स्थानान्तरण",
    "irr_status": "सिंचाई क्षेत्र की स्थिति",
    "alerts_title": "लाइव इंटेलिजेंस अलर्ट",
    "forecast_title": "5-दिवसीय पूर्वानुमान और सिंचाई दृष्टिकोण",
    "planner_title": "फसल-विशिष्ट सिंचाई योजनाकार",
    "savings_title": "जल और लागत बचत कैलकुलेटर",
    "score_100": "स्कोर / 100",
    "highest_level": "उच्चतम स्तर",
    "zones_action": "क्षेत्र जिन्हें कार्रवाई की आवश्यकता है",
    "target_crop": "लक्ष्य फसल",
    "analyze_needs": "आवश्यकताओं का विश्लेषण करें",
    "optimal": "इष्टतम",
    "water": "पानी",
    "savings_pct": "बचत प्रतिशत",
    "traditional": "पारंपरिक",
    "smart": "स्मार्ट",
    "cost_saved": "लागत बचत",
    "reposition_title": "उपकरण पुनर्स्थापन अनुसूची",
    "col_zone": "क्षेत्र",
    "col_stage": "चरण",
    "col_priority": "प्राथमिकता",
    "col_labor": "श्रम",
    "col_date": "तारीख",
    "col_status": "स्थिति"
  },
  "te": {
    "refresh": "↻ డేటా రిఫ్రెష్",
    "avg_sm": "సగటు నేల తేమ",
    "urgency": "మొత్తం అత్యవసరం",
    "drip": "సగటు డ్రిప్ ఆరోగ్యం",
    "repo": "పెండింగ్ మార్పులు",
    "irr_status": "నీటి పారుదల మండల స్థితి",
    "alerts_title": "లైవ్ ఇంటెలిజెన్స్ అలర్ట్‌లు",
    "forecast_title": "5-రోజుల సూచన & నీటి పారుదల అవుట్‌లుక్",
    "planner_title": "పంట-నిర్దిష్ట నీటి పారుదల ప్లానర్",
    "savings_title": "నీరు & ఖర్చు పొదుపు కాలిక్యులేటర్",
    "score_100": "స్కోరు / 100",
    "highest_level": "అత్యున్నత స్థాయి",
    "zones_action": "చర్య అవసరమైన మండలాలు",
    "target_crop": "టార్గెట్ పంట",
    "analyze_needs": "అవసరాలను విశ్లేషించండి",
    "optimal": "ఆప్టిమల్",
    "water": "నీరు",
    "savings_pct": "పొదుపు శాతం",
    "traditional": "సాంప్రదాయ",
    "smart": "స్మార్ట్",
    "cost_saved": "ఖర్చు ఆదా",
    "reposition_title": "పరికరాల మార్పిడి షెడ్యూల్",
    "col_zone": "మండలం",
    "col_stage": "దశ",
    "col_priority": "ప్రాధాన్యత",
    "col_labor": "కార్మికులు",
    "col_date": "తేదీ",
    "col_status": "స్థితి"
  },
  "bn": { "refresh": "↻ তথ্য রিফ্রেশ করুন", "avg_sm": "গড় মাটির আর্দ্রতা", "urgency": "সামগ্রিক জরুরি অবস্থা", "drip": "গড় ড্রিপ স্বাস্থ্য", "repo": "বকেয়া পুনঃস্থাপন", "irr_status": "সেচ অঞ্চলের অবস্থা", "alerts_title": "লাইভ ইন্টেলিজেন্স অ্যালার্ট", "forecast_title": "৫-দিনের পূর্বাভাস এবং সেচ দৃষ্টিভঙ্গি", "planner_title": "ফসল-নির্দিষ্ট সেচ পরিকল্পনাকারী", "savings_title": "জল এবং খরচ সাশ্রয় ক্যালকুলেটর" },
  "gu": { "refresh": "↻ ડેટા તાજો કરો", "avg_sm": "સરેરાશ જમીનમાં ભેજ", "urgency": "સમગ્ર તાકીદ", "drip": "સરેરાશ ડ્રિપ આરોગ્ય", "repo": "બાકી રિપોઝિશન", "irr_status": "સિચાઈ ઝોન સ્થિતિ", "alerts_title": "લાઇવ ઇન્ટેલિજન્સ એલર્ટ્સ", "forecast_title": "5-દિવસની આગાહી અને સિંચાઈ દૃષ્ટિકોણ", "planner_title": "પાક-વિશિષ્ટ સિંચાઈ આયોજક", "savings_title": "પાણી અને ખર્ચ બચત કેલ્ક્યુલેટર" },
  "pa": { "refresh": "↻ ਡੇਟਾ ਤਾਜ਼ਾ ਕਰੋ", "avg_sm": "ਔਸਤ ਮਿੱਟੀ ਦੀ ਨਮੀ", "urgency": "ਸਮੁੱਚੀ ਜ਼ਰੂਰੀ", "drip": "ਔਸਤ ਡ੍ਰਿੱਪ ਸਿਹਤ", "repo": "ਬਾਕੀ ਮੁੜ-ਸਥਾਪਨਾ", "irr_status": "ਸਿੰਚਾਈ ਜ਼ੋਨ ਦੀ ਸਥਿਤੀ", "alerts_title": "ਲਾਈਵ ਇੰਟੈਲੀਜੈਂਸ ਅਲਰਟ", "forecast_title": "5-ਦਿਨ ਦੀ ਭਵਿੱਖਬਾਣੀ ਅਤੇ ਸਿੰਚਾਈ ਦਾ ਨਜ਼ਰੀਆ", "planner_title": "ਫਸਲ-ਵਿਸ਼ੇਸ਼ ਸਿੰਚਾਈ ਯੋਜਨਾਕਾਰ", "savings_title": "ਪਾਣੀ ਅਤੇ ਲਾਗਤ ਬਚਤ ਕੈਲਕੁਲੇਟਰ" },
  "ml": { "refresh": "↻ ഡാറ്റ പുതുക്കുക", "avg_sm": "ശരാശരി മണ്ണിലെ ഈർപ്പം", "urgency": "മൊത്തത്തിലുള്ള അടിയന്തരാവസ്ഥ", "drip": "ശരാശരി ഡ്രിപ്പ് ഹെൽത്ത്", "repo": "മാറ്റിസ്ഥാപിക്കാനുള്ളവ", "irr_status": "ജലസേചന മേഖലയുടെ അവസ്ഥ", "alerts_title": "ലൈവ് ഇന്റലിജൻസ് അലേർട്ടുകൾ", "forecast_title": "5-ദിവസത്തെ കാലാവസ്ഥാ പ്രവചനവും ജലസേചന കാഴ്ചപ്പാടും", "planner_title": "വിള-നിർദ്ദിഷ്ട ജലസേചന പ്ലാനർ", "savings_title": "ജലവും ചെലവും ലാഭിക്കാനുള്ള കാൽക്കുലേറ്റർ" },
  "or": { "refresh": "↻ ତଥ୍ୟ ଅଦ୍ୟତନ କରନ୍ତୁ", "avg_sm": "ହାରାହାରି ମୃତ୍ତିକା ଆର୍ଦ୍ରତା", "urgency": "ସାମଗ୍ରିକ ଜରୁରୀ ପରିସ୍ଥିତି", "drip": "ହାରାହାରి ଡ୍ରିପ୍ ସ୍ୱାସ୍ଥ្យ", "repo": "ବାକି ରହିଥିବା ପୁନଃସ୍ଥାପନ", "irr_status": "ଜଳସେଚନ ଜୋନ୍ ସ୍ଥିତି", "alerts_title": "ସିଧାସଳଖ ଇଣ୍ଟେଲିଜେନ୍ସ ଆଲର୍ଟ", "forecast_title": "5-ଦିନର ପୂର୍ବାନୁମାନ ଏବଂ ଜଳସେଚନ ଦୃଷ୍ଟିକୋଣ", "planner_title": "ଫସଲ-ନିର୍ଦ୍ଦିଷ୍ଟ ଜଳସେଚନ ଯୋଜನಾକାରୀ", "savings_title": "ଜଳ ଏବଂ ଖର୍ଚ୍ଚ ସଞ୍ଚୟ କାଲକୁଲେଟର" }
};

// NOTE: All DOM element selectors are now initialized inside initDOMRefs()
// which is called at the start of init() after DOMContentLoaded fires.

/* ────────────────────────────────────────────────────────────────
   Core Orchestration
   ──────────────────────────────────────────────────────────────── */

async function init() {
  initDOMRefs(); // Populate all DOM references now that the DOM is ready
  const calcSavingsBtn = document.getElementById('calculate-savings-btn');
  const city = cityInput.value || 'Hyderabad';
  const lang = localStorage.getItem('irrigation_lang') || 'en';
  languageSelect.value = lang;
  
  translateUI(lang);
  await refreshAll(city, lang);
  
  refreshBtn.addEventListener('click', () => refreshAll(cityInput.value, languageSelect.value));
  languageSelect.addEventListener('change', (e) => {
    const newLang = e.target.value;
    localStorage.setItem('irrigation_lang', newLang);
    translateUI(newLang);
    refreshAll(cityInput.value, newLang);
  });
  getRecBtn.addEventListener('click', fetchCropRecommendation);
  calcSavingsBtn.addEventListener('click', fetchWaterSavings);
  ttsBtn.addEventListener('click', () => {
    const text = document.getElementById('rec-text').textContent;
    speakText(text, languageSelect.value);
  });
}

function translateUI(lang) {
  const t = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS['en'];
  refreshBtn.textContent = t.refresh;
  document.querySelector('#card-soil-moisture .metric-label').textContent = t.avg_sm;
  document.querySelector('#card-urgency .metric-label').textContent = t.urgency;
  document.querySelector('#card-drip-health .metric-label').textContent = t.drip;
  document.querySelector('#card-repositions .metric-label').textContent = t.repo;
  document.querySelector('.zone-section .section-title span').nextSibling.textContent = ' ' + t.irr_status;
  document.querySelector('.alert-section .section-title span').nextSibling.textContent = ' ' + t.alerts_title;
  document.querySelector('.forecast-section .section-title span').nextSibling.textContent = ' ' + t.forecast_title;
  document.querySelector('.crop-section .section-title span').nextSibling.textContent = ' ' + t.planner_title;
  document.querySelector('.savings-section .section-title span').nextSibling.textContent = ' ' + t.savings_title;

  // Translate zone labels
  const zoneLabels = document.querySelectorAll('.zone-metric-label');
  zoneLabels.forEach(label => {
    const text = label.textContent.trim().toLowerCase();
    if (text.includes('soil moisture')) {
      label.textContent = (lang === 'hi' ? 'मिट्टी की नमी' : (lang === 'te' ? 'నేలలో తేమ' : 'Soil Moisture'));
    }
  });
}

function speakText(text, lang) {
  console.log(`[TTS] Speaking in ${lang}: "${text.substring(0, 30)}..."`);
  if (!window.speechSynthesis) return showToast('TTS not supported', 'error');
  
  const langMap = {
    "hi": ["hi-IN", "hi"], "te": ["te-IN", "te"], "ta": ["ta-IN", "ta"], "kn": ["kn-IN", "kn"],
    "mr": ["mr-IN", "mr"], "bn": ["bn-IN", "bn"], "gu": ["gu-IN", "gu"], "pa": ["pa-IN", "pa"],
    "ml": ["ml-IN", "ml"], "or": ["or-IN", "or"], "en": ["en-IN", "en-US", "en"]
  };
  
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  const targetLangs = langMap[lang] || [lang];
  utterance.lang = targetLangs[0];

  const updateVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    console.log(`[TTS] ${voices.length} voices available.`);
    
    // Attempt to find a voice matching any of our target codes
    let voice = null;
    for (const code of targetLangs) {
      voice = voices.find(v => v.lang.toLowerCase().replace('_', '-') === code.toLowerCase());
      if (voice) break;
    }
    
    // Fallback: search for voice starting with language code (e.g. "hi")
    if (!voice) {
      voice = voices.find(v => v.lang.toLowerCase().startsWith(lang.toLowerCase()));
    }

    if (voice) {
      console.log(`[TTS] Selected voice: ${voice.name} (${voice.lang})`);
      utterance.voice = voice;
    } else {
      console.warn(`[TTS] No specific voice found for ${lang}. Falling back to default.`);
    }
    window.speechSynthesis.speak(utterance);
  };

  if (window.speechSynthesis.getVoices().length > 0) {
    updateVoice();
  } else {
    window.speechSynthesis.onvoiceschanged = updateVoice;
  }
}

async function refreshAll(city, lang = 'en') {
  console.log(`[Dashboard] Refreshing for ${city} in ${lang}...`);
  if (!city) return showToast('Please enter a city', 'error');
  
  loadingOverlay.classList.add('active');
  try {
    console.log(`[Dashboard] Fetching from ${BASE_URL}...`);
    const [summary, forecast, history] = await Promise.all([
      fetch(`${BASE_URL}/dashboard-summary?city=${city}&lang=${lang}`).then(r => {
        if (!r.ok) throw new Error(`Summary API error: ${r.status}`);
        return r.json();
      }),
      fetchForecast(city),
      fetchHistoryChart()
    ]);

    console.log('[Dashboard] Data received:', summary);
    renderSummary(summary);
    renderZoneCards(summary.field_status, summary.drip_health);
    renderRepositionTable(summary.reposition_plan);
    fetchAlerts(); 
  } catch (err) {
    console.error('[Dashboard] Error during sync:', err);
    showToast('Failed to sync intelligence: ' + err.message, 'error');
  } finally {
    loadingOverlay.classList.remove('active');
  }
}

/* ────────────────────────────────────────────────────────────────
   FEATURE 1: Weather Forecast
   ──────────────────────────────────────────────────────────────── */

async function fetchForecast(city) {
  try {
    const res = await fetch(`${BASE_URL}/forecast?city=${city}`);
    const data = await res.json();
    
    forecastRow.innerHTML = data.map(day => {
      const smColor = day.predicted_soil_moisture > 60 ? '#52B788' : (day.predicted_soil_moisture > 35 ? '#F4A261' : '#E63946');
      const rainBadge = day.rainfall > 5 ? '<div class="rain-badge">Rain expected — reduce irrigation</div>' : '';
      
      return `
        <div class="forecast-card">
          <div class="forecast-day">${day.day_name}</div>
          <div class="forecast-date">${day.date}</div>
          <img class="forecast-icon" src="https://openweathermap.org/img/wn/${day.icon_code}@2x.png" alt="weather">
          <div class="forecast-temp">${Math.round(day.temp)}°C</div>
          <div class="forecast-desc">${day.description}</div>
          ${rainBadge}
          <div class="forecast-soil-bar" style="background: ${smColor}" title="Predicted Soil Moisture: ${day.predicted_soil_moisture}%"></div>
        </div>
      `;
    }).join('');
    
    return data;
  } catch (err) { console.error('Forecast failed', err); }
}

/* ────────────────────────────────────────────────────────────────
   FEATURE 2: Crop Recommendations
   ──────────────────────────────────────────────────────────────── */

async function fetchCropRecommendation() {
  const city = cityInput.value;
  const crop = cropSelect.value;
  const lang = languageSelect.value;
  
  try {
    const res = await fetch(`${BASE_URL}/crop-recommendation?city=${city}&crop=${crop}&lang=${lang}`);
    const data = await res.json();
    
    cropResultCard.classList.remove('hidden');
    cropResultCard.className = 'crop-result-card' + (data.irrigate_now ? ' irrigate' : '');
    
    document.getElementById('rec-crop-name').textContent = data.crop;
    document.getElementById('rec-text').textContent = data.recommendation_text;
    document.getElementById('rec-optimal').textContent = data.optimal_soil_moisture;
    document.getElementById('rec-water').textContent = data.adjusted_water_litres;
    
    const badge = document.getElementById('irrigate-badge');
    const irrigateText = languageSelect.value === 'hi' ? 'अब सिंचाई करें' : (languageSelect.value === 'te' ? 'ఇప్పుడే నీరు పెట్టండి' : (data.irrigate_now ? 'Irrigate Now' : 'Skip Today'));
    badge.textContent = irrigateText;
    badge.className = 'irrigate-badge ' + (data.irrigate_now ? 'red' : 'green');
    
    const gauge = document.getElementById('soil-gauge');
    gauge.setAttribute('data-value', Math.round(data.soil_moisture_score));
    gauge.style.background = `conic-gradient(${data.irrigate_now ? '#E63946' : '#52B788'} ${data.soil_moisture_score}%, #eee 0%)`;
    
    showToast('Recommendation updated for ' + crop);
  } catch (err) { showToast('Planner error', 'error'); }
}

/* ────────────────────────────────────────────────────────────────
   FEATURE 3: Live Alerts System
   ──────────────────────────────────────────────────────────────── */

async function fetchAlerts() {
  try {
    const res = await fetch(`${BASE_URL}/alerts`);
    const alerts = await res.json();
    
    alertCount.textContent = `${alerts.length} alert${alerts.length !== 1 ? 's' : ''}`;
    
    if (alerts.length === 0) {
      alertList.innerHTML = '<div class="alert-empty">✅ All systems nominal — no active alerts</div>';
      return;
    }
    
    alertList.innerHTML = alerts.map(a => `
      <div class="alert-item ${a.severity}">
        <div class="severity-dot ${a.severity}"></div>
        <div class="alert-content">
          <div class="alert-title">${a.zone} Zone: ${a.alert_type}</div>
          <div class="alert-msg">${a.message}</div>
        </div>
        <button class="resolve-btn" onclick="resolveAlert(${a.id})">Mark Resolved</button>
      </div>
    `).join('');
  } catch (err) { console.error('Alert fetch failed', err); }
}

async function resolveAlert(id) {
  try {
    await fetch(`${BASE_URL}/alerts/${id}/resolve`, { method: 'POST' });
    showToast('Alert resolved');
    fetchAlerts();
  } catch (err) { showToast('Failed to resolve', 'error'); }
}

/* ────────────────────────────────────────────────────────────────
   FEATURE 4: History Chart (Line)
   ──────────────────────────────────────────────────────────────── */

async function fetchHistoryChart() {
  try {
    const res = await fetch(`${BASE_URL}/history-chart?days=7`);
    const data = await res.json();
    
    const ctx = document.getElementById('soil-chart').getContext('2d');
    
    if (soilChart) soilChart.destroy();
    
    const datasets = [
      {
        label: 'Average',
        data: data.avg_moisture,
        borderColor: '#1B4332',
        borderWidth: 4,
        tension: 0.4,
        fill: false
      }
    ];
    
    const colors = ['#40916C', '#F4A261', '#E63946', '#185FA5'];
    Object.keys(data.zones).forEach((zone, i) => {
      datasets.push({
        label: zone,
        data: data.zones[zone],
        borderColor: colors[i],
        borderWidth: 2,
        tension: 0.4,
        fill: false,
        hidden: false
      });
    });

    soilChart = new Chart(ctx, {
      type: 'line',
      data: { labels: data.dates, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } } },
        scales: { y: { min: 0, max: 100 } }
      }
    });
    
  } catch (err) { console.error('Chart failed', err); }
}

/* ────────────────────────────────────────────────────────────────
   FEATURE 5: Water Savings Calculator
   ──────────────────────────────────────────────────────────────── */

async function fetchWaterSavings() {
  const city = cityInput.value;
  const area = areaInput.value;
  const crop = cropSelect.value;
  const lang = languageSelect.value;
  
  try {
    const res = await fetch(`${BASE_URL}/water-savings?city=${city}&area_hectares=${area}&crop=${crop}&lang=${lang}`);
    const data = await res.json();
    
    animateCounter('savings-pct', data.savings_percent, '%');
    document.getElementById('trad-water').textContent = data.traditional_water.toLocaleString();
    document.getElementById('smart-water').textContent = data.smart_water.toLocaleString();
    document.getElementById('cost-saved').textContent = '₹' + data.cost_saved_inr.toLocaleString();
  } catch (err) { showToast('Savings calc error', 'error'); }
}

function animateCounter(id, target, suffix = '') {
  let current = 0;
  const el = document.getElementById(id);
  const step = target / 50;
  const interval = setInterval(() => {
    current += step;
    if (current >= target) {
      el.textContent = target + suffix;
      clearInterval(interval);
    } else {
      el.textContent = Math.round(current) + suffix;
    }
  }, 20);
}

/* ────────────────────────────────────────────────────────────────
   FEATURE 6: Exports
   ──────────────────────────────────────────────────────────────── */

function exportData(table) {
  window.location.href = `${BASE_URL}/export/csv?table=${table}`;
}

function downloadReport() {
  const city = cityInput.value || 'Hyderabad';
  window.location.href = `${BASE_URL}/export/report?city=${city}`;
}

/* ────────────────────────────────────────────────────────────────
   Rendering Helpers (Ported/Adapted)
   ──────────────────────────────────────────────────────────────── */

function renderSummary(data) {
  const avg = (data.field_status.reduce((s, z) => s + z.soil_moisture_score, 0) / 4).toFixed(1);
  skeletonOff('avg-soil-moisture', avg);
  
  const urgencies = data.field_status.map(z => z.urgency);
  const status = urgencies.includes('critical') ? 'Critical' : (urgencies.includes('high') ? 'High' : 'Low');
  skeletonOff('overall-urgency', status);
  
  const avgDrip = (data.drip_health.reduce((s, z) => s + z.health_score, 0) / 4).toFixed(1);
  skeletonOff('avg-drip-health', avgDrip);
  
  const pending = data.reposition_plan.filter(p => p.priority_score > 10).length;
  skeletonOff('pending-repositions', pending);
}

function renderZoneCards(fields, drips) {
  ['North', 'South', 'East', 'West'].forEach(z => {
    const f = fields.find(x => x.zone === z);
    const d = drips.find(x => x.zone === z);
    const zk = z.toLowerCase();
    
    const sm = f.soil_moisture_score;
    document.getElementById(`sm-${zk}`).textContent = sm + '%';
    const fill = document.getElementById(`progress-${zk}`);
    fill.style.width = sm + '%';
    fill.className = 'progress-fill ' + (sm > 60 ? '' : (sm > 35 ? 'amber' : 'red'));
    
    document.getElementById(`drip-${zk}`).textContent = d.health_score + '%';
    document.getElementById(`health-${zk}`).style.width = d.health_score + '%';
    document.getElementById(`fault-${zk}`).textContent = d.fault_type !== 'none' ? '⚠ ' + d.fault_type : '';
    
    document.getElementById(`temp-${zk}`).textContent = `🌡️ ${f.temperature}°C`;
    document.getElementById(`hum-${zk}`).textContent = `💦 ${f.humidity}%`;
    document.getElementById(`desc-${zk}`).textContent = `🌤️ ${f.weather_description}`;
    
    const badge = document.getElementById(`urgency-${zk}`);
    badge.textContent = f.urgency.toUpperCase();
    badge.className = 'urgency-badge ' + f.urgency;
  });
}

function renderRepositionTable(plan) {
  repositionTbody.innerHTML = plan.map(p => `
    <tr>
      <td><b>${p.zone}</b></td>
      <td>${p.crop_stage}</td>
      <td>${p.priority_score.toFixed(1)}</td>
      <td>${p.labor_hours}h</td>
      <td>${p.recommended_date}</td>
      <td><span class="status-badge-table ${p.priority_score > 10 ? 'soon' : 'scheduled'}">${p.priority_score > 10 ? 'Urgent' : 'OK'}</span></td>
    </tr>
  `).join('');
}

function skeletonOff(id, val) {
  const el = document.getElementById(id);
  el.classList.remove('skeleton');
  el.textContent = val;
}

function showToast(msg, type = 'success') {
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  toastContainer.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// Global scope for HTML onclick
window.exportData = exportData;
window.downloadReport = downloadReport;
window.resolveAlert = resolveAlert;

document.addEventListener('DOMContentLoaded', init);
