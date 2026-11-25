import {
  Camera,
  CheckCircle2,
  Compass,
  FileText,
  HelpCircle,
  Lock,
  MapPin,
  PhoneCall,
  Search,
  Sprout,
  Type,
  Users,
} from 'lucide-react';
import { useState } from 'react';
import { AdvisoryCard } from './components/AdvisoryCard';
import { ClaimTracker } from './components/ClaimTracker';
import { EvaluatorControls } from './components/EvaluatorControls';
import { GuidedCameraModal } from './components/GuidedCameraModal';
import { MoneyMapCard } from './components/MoneyMapCard';
import { PMFBYRulesModal } from './components/PMFBYRulesModal';
import { WhatsAppReceipt } from './components/WhatsAppReceipt';
import { SAMPLE_PLOTS, SCENARIO_DATA } from './data/tumakuruData';
import type {
  CapturedPhotoProof,
  CultivatorStatus,
  Language,
  PlotRecord,
  StressScenario,
  TextZoom,
} from './types';

export function App() {
  const [lang, setLang] = useState<Language>('kn');
  const [textZoom, setTextZoom] = useState<TextZoom>('normal');
  const [cultivatorStatus, setCultivatorStatus] = useState<CultivatorStatus>('landowner');
  const [consentGiven, setConsentGiven] = useState<boolean>(true);
  const [surveyQuery, setSurveyQuery] = useState<string>('Sy. No. 142/3, Gubbi Taluk, Tumakuru');
  const [activePlot, setActivePlot] = useState<PlotRecord | null>(null);

  // Evaluator demo & live pipeline state
  const [scenario, setScenario] = useState<StressScenario>('drought');
  const [offlineMode, setOfflineMode] = useState<boolean>(false);
  const [queuedCount, setQueuedCount] = useState<number>(0);
  const [claimStage, setClaimStage] = useState<number>(2);
  const [voiceLossLogged, setVoiceLossLogged] = useState<boolean>(false);

  // Modals & notifications
  const [rulesOpen, setRulesOpen] = useState<boolean>(false);
  const [cameraOpen, setCameraOpen] = useState<boolean>(false);
  const [receiptOpen, setReceiptOpen] = useState<boolean>(false);
  const [capturedProof, setCapturedProof] = useState<CapturedPhotoProof | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const isKn = lang === 'kn';
  const telemetry = SCENARIO_DATA[scenario];

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  const handleLoadPlot = (plot: PlotRecord) => {
    if (!consentGiven) {
      showToast(
        isKn
          ? 'ದಯವಿಟ್ಟು ಮೊದಲು AgriStack/ಭೂಮಿ ದಾಖಲೆ ಒಪ್ಪಿಗೆಯನ್ನು ಆನ್ ಮಾಡಿ.'
          : 'Please enable the plain-language land record consent toggle first.'
      );
      return;
    }
    setActivePlot(plot);
    showToast(
      isKn
        ? `📍 ${plot.surveyNo} (${plot.taluk}) ಜಮೀನು ಲೋಡ್ ಆಗಿದೆ`
        : `📍 Loaded ${plot.surveyNo}, ${plot.taluk} (${plot.crop})`
    );
  };

  const handleSurveyLookup = () => {
    const q = surveyQuery.toLowerCase();
    const matched =
      SAMPLE_PLOTS.find(
        (p) =>
          q.includes(p.surveyNo.toLowerCase()) ||
          q.includes(p.taluk.toLowerCase()) ||
          q.includes(p.ulpin.toLowerCase())
      ) || SAMPLE_PLOTS[0];
    handleLoadPlot(matched);
  };

  const handlePhotoCaptured = (proof: CapturedPhotoProof) => {
    setCapturedProof(proof);
    if (offlineMode) {
      setQueuedCount((c) => c + 1);
    }
    setClaimStage((s) => Math.max(s, 2));
    setCameraOpen(false);
    setReceiptOpen(true);

    // Sensory confirmation toast in Kannada
    showToast('ನಿಮ್ಮ ಹೊಲದ ಫೋಟೋ ಯಶಸ್ವಿಯಾಗಿ ದಾಖಲಾಗಿದೆ');
    if ('speechSynthesis' in window) {
      try {
        const u = new SpeechSynthesisUtterance('ನಿಮ್ಮ ಹೊಲದ ಫೋಟೋ ಯಶಸ್ವಿಯಾಗಿ ದಾಖಲಾಗಿದೆ');
        u.lang = 'kn-IN';
        window.speechSynthesis.speak(u);
      } catch {
        // Ignore speech synthesis errors on headless browsers
      }
    }
  };

  const handleSyncQueue = () => {
    setOfflineMode(false);
    setQueuedCount(0);
    if (capturedProof) {
      setCapturedProof({ ...capturedProof, synced: true });
    }
    showToast(
      isKn
        ? '✅ ಆಫ್‌ಲೈನ್ ದಾಖಲೆಗಳು AIC/PMFBY ಸರ್ವರ್‌ಗೆ ಸಿಂಕ್ ಆಗಿವೆ'
        : '✅ Offline queue synced to AIC/PMFBY audit pipeline'
    );
  };

  return (
    <div
      className={`min-h-screen bg-[#f6f8f4] text-slate-900 pb-24 ${
        textZoom === 'large' ? 'text-[17px] sm:text-lg' : 'text-sm sm:text-base'
      }`}
    >
      {/* ── Top Sticky Bharat-First Header ────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b border-emerald-900/10 bg-white/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-2 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-900 text-white shadow-xs">
              <Sprout className="h-5 w-5 text-emerald-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-extrabold tracking-tight text-slate-900">
                  SookshmaJal
                </span>
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-extrabold text-emerald-900">
                  VECTORZZ
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-500">
                {isKn ? 'ತುಮಕೂರು · ನೀರಾವರಿ & PMFBY ರಕ್ಷಣೆ' : 'Tumakuru · Irrigation & PMFBY Trust'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Language Switcher: ಕನ್ನಡ | English */}
            <div
              className="inline-flex rounded-full border border-slate-300 bg-slate-100 p-0.5"
              role="group"
              aria-label="Language switcher"
            >
              <button
                type="button"
                onClick={() => setLang('kn')}
                className={`rounded-full px-3 py-1 text-xs font-extrabold transition ${
                  lang === 'kn' ? 'bg-emerald-900 text-white shadow-xs' : 'text-slate-700'
                }`}
              >
                ಕನ್ನಡ
              </button>
              <button
                type="button"
                onClick={() => setLang('en')}
                className={`rounded-full px-3 py-1 text-xs font-extrabold transition ${
                  lang === 'en' ? 'bg-emerald-900 text-white shadow-xs' : 'text-slate-700'
                }`}
              >
                English
              </button>
            </div>

            {/* Persistent Text Zoom Toggle */}
            <button
              type="button"
              onClick={() => setTextZoom((z) => (z === 'normal' ? 'large' : 'normal'))}
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-bold transition ${
                textZoom === 'large'
                  ? 'border-emerald-700 bg-emerald-50 text-emerald-900'
                  : 'border-slate-300 bg-white text-slate-700'
              }`}
              title="Toggle UI Text Size"
            >
              <Type className="h-3.5 w-3.5" />
              <span>{textZoom === 'large' ? 'Large A+' : 'Normal A'}</span>
            </button>

            {/* PMFBY Rules & Eligibility Quick Access */}
            <button
              type="button"
              onClick={() => setRulesOpen(true)}
              className="inline-flex items-center gap-1 rounded-full border border-emerald-700/30 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-900 hover:bg-emerald-100"
            >
              <HelpCircle className="h-3.5 w-3.5" />
              <span>{isKn ? 'PMFBY ನಿಯಮಗಳು' : 'PMFBY Rules'}</span>
            </button>

            {/* Subtle Top-Right Evaluator Demo Drawer */}
            <EvaluatorControls
              lang={lang}
              scenario={scenario}
              onChangeScenario={setScenario}
              offlineMode={offlineMode}
              onToggleOffline={() => setOfflineMode((o) => !o)}
              queuedCount={queuedCount}
              onSyncQueue={handleSyncQueue}
              claimStage={claimStage}
              onAdvanceStage={() => setClaimStage((s) => Math.min(5, s + 1))}
              onResetStages={() => {
                setClaimStage(2);
                setVoiceLossLogged(false);
              }}
            />
          </div>
        </div>
      </header>

      {/* ── Main Content ─────────────────────────────────────────────── */}
      <main className="mx-auto max-w-4xl space-y-6 px-4 pt-5">
        {/* SCREEN 1: Low-Cognitive-Load Land & Plot Lookup */}
        <section
          className="rounded-3xl border-2 border-emerald-900/15 bg-white p-5 shadow-sm"
          aria-labelledby="lookup-heading"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <div>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-extrabold text-emerald-900">
                1 · {isKn ? 'ಜಮೀನು ಗುರುತಿಸುವಿಕೆ' : 'Step 1 · Land & Plot Lookup'}
              </span>
              <h1 id="lookup-heading" className="text-xl sm:text-2xl font-extrabold text-slate-900 mt-1">
                {isKn
                  ? 'ನಿಮ್ಮ ಹೊಲವನ್ನು ಸುಲಭವಾಗಿ ಆಯ್ಕೆ ಮಾಡಿ'
                  : 'Find Your Farm Plot in One Tap'}
              </h1>
            </div>
            <button
              type="button"
              onClick={() => setRulesOpen(true)}
              className="text-xs font-bold text-emerald-800 underline underline-offset-2"
            >
              {isKn ? 'PMFBY ಅರ್ಹತೆ & ನಿಯಮಗಳು →' : 'PMFBY Rules & Eligibility →'}
            </button>
          </div>

          {/* Cultivator Status Toggle */}
          <div className="mb-4">
            <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">
              <Users className="inline h-3.5 w-3.5 mr-1 text-emerald-700" />
              {isKn ? 'ರೈತರ ಸ್ಥಿತಿ (Cultivator Status)' : 'Cultivator Status'}
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setCultivatorStatus('landowner')}
                className={`rounded-2xl border-2 px-4 py-3 text-left transition ${
                  cultivatorStatus === 'landowner'
                    ? 'border-emerald-800 bg-emerald-50 text-emerald-950'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                <div className="text-sm font-extrabold">
                  {isKn ? 'ಖಾತೆದಾರ (Landowner)' : 'Landowner (ಖಾತೆದಾರ)'}
                </div>
                <div className="text-[11px] text-slate-600 mt-0.5">
                  {isKn ? 'RTC / ಪಹಣಿ ಆಧಾರಿತ ವಿಮೆ' : 'Direct RTC / Pahani link'}
                </div>
              </button>
              <button
                type="button"
                onClick={() => setCultivatorStatus('tenant')}
                className={`rounded-2xl border-2 px-4 py-3 text-left transition ${
                  cultivatorStatus === 'tenant'
                    ? 'border-emerald-800 bg-emerald-50 text-emerald-950'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                <div className="text-sm font-extrabold">
                  {isKn ? 'ಗೇಣಿದಾರ (Tenant / Sharecropper)' : 'Tenant / Sharecropper (ಗೇಣಿದಾರ)'}
                </div>
                <div className="text-[11px] text-slate-600 mt-0.5">
                  {isKn ? 'ಗೇಣಿ ಪತ್ರದೊಂದಿಗೆ PMFBY ಅರ್ಹರು' : 'Eligible with tenancy proof'}
                </div>
              </button>
            </div>
          </div>

          {/* Plain-Language OAuth-style Consent Toggle */}
          <div className="mb-4 rounded-2xl border border-slate-200 bg-stone-50 p-3.5 flex items-center justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <Lock className="h-4 w-4 text-emerald-700 shrink-0 mt-1" />
              <div className="text-xs sm:text-sm">
                <div className="font-bold text-slate-900">
                  {isKn
                    ? 'ಭೂಮಿ / AgriStack ದಾಖಲೆ ಪಡೆಯಲು ಒಪ್ಪಿಗೆ'
                    : 'Plain-Language Land Record Consent'}
                </div>
                <p className="text-slate-600 text-xs">
                  {isKn
                    ? 'ನಿಮ್ಮ ಸರ್ವೆ ಸಂಖ್ಯೆ ಮತ್ತು ಬೆಳೆ ವಿವರವನ್ನು ನೀರಾವರಿ ಹಾಗೂ PMFBY ಪರಿಶೀಲನೆಗೆ ಮಾತ್ರ ಬಳಸಲಾಗುತ್ತದೆ.'
                    : 'Used strictly to fetch your Dishaank/Bhoomi parcel boundary & calculate your PMFBY Sum Insured.'}
                </p>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={consentGiven}
              onClick={() => setConsentGiven((c) => !c)}
              className={`relative inline-flex h-7 w-12 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                consentGiven ? 'bg-emerald-700' : 'bg-slate-300'
              }`}
              aria-label="Toggle land record consent"
            >
              <span
                className={`inline-block h-6 w-6 transform rounded-full bg-white shadow-sm transition ${
                  consentGiven ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* Two Friction-Free Entry Options */}
          <div className="grid sm:grid-cols-2 gap-3">
            {/* Option 1: 1-Click GPS Dishaank Mode */}
            <button
              type="button"
              onClick={() => handleLoadPlot(SAMPLE_PLOTS[0])}
              className="flex items-center justify-center gap-2.5 rounded-2xl bg-emerald-900 px-5 py-4 text-sm sm:text-base font-extrabold text-white shadow-sm hover:bg-emerald-950 transition"
            >
              <Compass className="h-5 w-5 text-emerald-300 shrink-0" />
              <span>
                {isKn
                  ? 'GPS ಮೂಲಕ ಹೊಲ ಪತ್ತೆ ಮಾಡಿ (Dishaank)'
                  : 'Detect My Plot via GPS (Dishaank Mode)'}
              </span>
            </button>

            {/* Option 2: Single Survey / ULPIN Lookup */}
            <div className="flex gap-2">
              <input
                type="text"
                value={surveyQuery}
                onChange={(e) => setSurveyQuery(e.target.value)}
                aria-label="Survey number or ULPIN"
                className="flex-1 min-w-0 rounded-2xl border-2 border-slate-300 bg-white px-3.5 py-3 text-sm font-semibold text-slate-900 focus:border-emerald-700 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleSurveyLookup}
                className="inline-flex items-center gap-1.5 rounded-2xl bg-emerald-100 border-2 border-emerald-700/25 px-4 py-3 text-sm font-extrabold text-emerald-950 hover:bg-emerald-200 transition shrink-0"
              >
                <Search className="h-4 w-4" />
                <span>{isKn ? 'ಹುಡುಕಿ' : 'Lookup'}</span>
              </button>
            </div>
          </div>

          {/* Quick Sample Parcel Pills */}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold text-slate-500">
              {isKn ? 'ಮಾದರಿ ತುಮಕೂರು ಜಮೀನುಗಳು:' : 'Sample Tumakuru Parcels:'}
            </span>
            {SAMPLE_PLOTS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setSurveyQuery(`${p.surveyNo}, ${p.taluk} Taluk, ${p.district}`);
                  handleLoadPlot(p);
                }}
                className={`rounded-full px-3 py-1 font-bold border transition ${
                  activePlot?.id === p.id
                    ? 'bg-emerald-900 text-white border-emerald-900'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                <MapPin className="inline h-3 w-3 mr-1" />
                {p.surveyNo} · {p.taluk} ({isKn ? p.cropKn : p.crop.split(' ')[0]})
              </button>
            ))}
          </div>
        </section>

        {/* Active Plot Banner + Screens 2, 3, 4 */}
        {activePlot && (
          <>
            {/* Selected Plot Summary Strip */}
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-emerald-900 px-4 py-3 text-white shadow-xs">
              <div className="flex items-center gap-2 text-xs sm:text-sm font-bold">
                <CheckCircle2 className="h-4 w-4 text-emerald-300 shrink-0" />
                <span>
                  {isKn ? activePlot.farmerNameKn : activePlot.farmerName} · {activePlot.surveyNo},{' '}
                  {activePlot.village}, {activePlot.taluk} ({activePlot.areaAcres} ac ·{' '}
                  {isKn ? activePlot.cropKn : activePlot.crop})
                </span>
              </div>
              <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-[11px] font-mono">
                ULPIN: {activePlot.ulpin}
              </span>
            </div>

            {/* SCREEN 2: The Money Map & 7-Day FAO-56 Advisory */}
            <div className="grid gap-6 md:grid-cols-2">
              <MoneyMapCard
                plot={activePlot}
                lang={lang}
                onOpenRules={() => setRulesOpen(true)}
              />
              <AdvisoryCard plot={activePlot} telemetry={telemetry} lang={lang} />
            </div>

            {/* SCREEN 3: Guided In-App Field Camera Trigger */}
            <section className="rounded-3xl border-2 border-emerald-900/15 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-extrabold text-amber-900">
                    3 · {isKn ? 'ಲೈವ್ ಜಿಯೋಟ್ಯಾಗ್ ಕ್ಷೇತ್ರ ಸಾಕ್ಷ್ಯ' : 'Step 3 · Guided Field Camera'}
                  </span>
                  <h2 className="text-lg font-extrabold text-slate-900">
                    {isKn
                      ? 'ಬೆಳೆ ರೋಗನಿರ್ಣಯ ಮತ್ತು SHA-256 ಫೋಟೋ ದಾಖಲಾತಿ'
                      : 'Instant Crop Diagnosis & Tamper-Proof Photo Proof'}
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-600">
                    {isKn
                      ? 'ಗ್ಯಾಲರಿ ಅಪ್‌ಲೋಡ್ ನಿರ್ಬಂಧಿತವಾಗಿದೆ — ನೇರ ಜಿಯೋಟ್ಯಾಗ್ ಕ್ಯಾಮೆರಾ ದಾವೆ ತಿರಸ್ಕಾರವನ್ನು ತಡೆಯುತ್ತದೆ.'
                      : 'Live geotagged capture only — prevents insurer rejection and generates a WhatsApp QR receipt.'}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2.5">
                  <button
                    type="button"
                    onClick={() => setCameraOpen(true)}
                    className="inline-flex items-center gap-2 rounded-2xl bg-emerald-700 px-5 py-3.5 text-sm font-extrabold text-white shadow-sm hover:bg-emerald-800 transition"
                  >
                    <Camera className="h-5 w-5" />
                    <span>
                      {isKn ? '📸 ಕ್ಷೇತ್ರ ಕ್ಯಾಮೆರಾ ತೆರೆಯಿರಿ' : '📸 Open Guided Field Camera'}
                    </span>
                  </button>
                  {capturedProof && (
                    <button
                      type="button"
                      onClick={() => setReceiptOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-2xl border-2 border-emerald-700 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-900 hover:bg-emerald-100"
                    >
                      <FileText className="h-4 w-4" />
                      <span>{isKn ? 'QR ರಸೀದಿ ನೋಡಿ' : 'View QR Receipt'}</span>
                    </button>
                  )}
                </div>
              </div>
            </section>

            {/* SCREEN 4: 5-Stage Live Claim & Verification Tracker */}
            <ClaimTracker
              lang={lang}
              plot={activePlot}
              telemetry={telemetry}
              proof={capturedProof}
              claimStage={claimStage}
              voiceLossLogged={voiceLossLogged}
              onLogVoiceLoss={() => {
                setVoiceLossLogged(true);
                setClaimStage((s) => Math.max(s, 2));
                showToast(
                  isKn
                    ? '🎙 ಧ್ವನಿ ಬೆಳೆ ನಷ್ಟ ವರದಿ ದಾಖಲಾಗಿದೆ — 5-ಹಂತದ ಪರಿಶೀಲನೆ ಆರಂಭವಾಗಿದೆ'
                    : '🎙 Voice loss note logged — 5-stage PMFBY verification started'
                );
              }}
              onOpenRules={() => setRulesOpen(true)}
            />
          </>
        )}
      </main>

      {/* ── Persistent Bharat-First Escalation Footer Bar ─────────────── */}
      <div className="fixed bottom-0 inset-x-0 z-30 border-t border-emerald-900/15 bg-white/95 backdrop-blur-md px-4 py-2.5">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3">
          <div className="text-xs text-slate-600 hidden sm:block">
            <strong>SookshmaJal</strong> · {isKn ? 'ಅಧಿಕೃತ PMFBY ಸಹಾಯ' : 'Official PMFBY Support'} ·{' '}
            <button
              type="button"
              onClick={() => setRulesOpen(true)}
              className="font-bold text-emerald-800 underline"
            >
              {isKn ? 'ನಿಯಮಗಳು & ಅರ್ಹತೆ' : 'Rules & Checklist'}
            </button>
          </div>
          <a
            href="tel:14447"
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 rounded-full bg-emerald-900 px-5 py-2.5 text-sm font-extrabold text-white shadow-md hover:bg-emerald-950 transition"
          >
            <PhoneCall className="h-4 w-4 text-emerald-300" />
            <span>ಸಹಾಯ / Call Krishi Mitra (14447)</span>
          </a>
        </div>
      </div>

      {/* ── Toast Notification ───────────────────────────────────────── */}
      {toastMsg && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 rounded-full bg-slate-900 px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-xl"
        >
          {toastMsg}
        </div>
      )}

      {/* ── Modals ───────────────────────────────────────────────────── */}
      <PMFBYRulesModal
        isOpen={rulesOpen}
        onClose={() => setRulesOpen(false)}
        lang={lang}
        plot={activePlot}
        cultivatorStatus={cultivatorStatus}
        consentGiven={consentGiven}
        capturedProof={capturedProof}
      />

      {activePlot && (
        <>
          <GuidedCameraModal
            isOpen={cameraOpen}
            onClose={() => setCameraOpen(false)}
            lang={lang}
            plot={activePlot}
            telemetry={telemetry}
            offlineMode={offlineMode}
            onCaptured={handlePhotoCaptured}
            onOpenRules={() => setRulesOpen(true)}
          />
          <WhatsAppReceipt
            isOpen={receiptOpen}
            onClose={() => setReceiptOpen(false)}
            lang={lang}
            plot={activePlot}
            proof={capturedProof}
          />
        </>
      )}
    </div>
  );
}

export default App;
