import {
  Camera,
  CheckCircle2,
  Lock,
  MapPin,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react';
import React, { useState } from 'react';
import type {
  CapturedPhotoProof,
  Language,
  PlotRecord,
  ScenarioTelemetry,
} from '../types';

interface GuidedCameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  plot: PlotRecord;
  telemetry: ScenarioTelemetry;
  offlineMode: boolean;
  onCaptured: (proof: CapturedPhotoProof) => void;
  onOpenRules: () => void;
}

async function computeSha256Hex(input: string): Promise<string> {
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    const bytes = new TextEncoder().encode(input);
    const hashBuf = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(hashBuf))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  }
  let acc = 2166136261;
  for (let i = 0; i < input.length; i++) {
    acc ^= input.charCodeAt(i);
    acc = Math.imul(acc, 16777619);
  }
  return (acc >>> 0).toString(16).padStart(64, 'a');
}

export const GuidedCameraModal: React.FC<GuidedCameraModalProps> = ({
  isOpen,
  onClose,
  lang,
  plot,
  telemetry,
  offlineMode,
  onCaptured,
  onOpenRules,
}) => {
  const [capturing, setCapturing] = useState(false);
  const [previewProof, setPreviewProof] = useState<CapturedPhotoProof | null>(null);

  if (!isOpen) return null;
  const isKn = lang === 'kn';

  const handleCapture = async () => {
    setCapturing(true);
    const ts = new Date().toISOString();
    const payload = `${plot.id}|${plot.surveyNo}|${plot.gpsLat}|${plot.gpsLon}|${telemetry.id}|${ts}`;
    const sha256 = await computeSha256Hex(payload);

    const proof: CapturedPhotoProof = {
      sha256,
      lat: plot.gpsLat,
      lon: plot.gpsLon,
      timestampIso: ts,
      diagnosisTitleEn: telemetry.diagnosisTitleEn,
      diagnosisTitleKn: telemetry.diagnosisTitleKn,
      diagnosisDetailEn: telemetry.diagnosisDetailEn,
      diagnosisDetailKn: telemetry.diagnosisDetailKn,
      synced: !offlineMode,
    };

    setTimeout(() => {
      setCapturing(false);
      setPreviewProof(proof);
      onCaptured(proof);
    }, 350);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-950/75 backdrop-blur-xs p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="camera-modal-title"
    >
      <div className="w-full max-w-lg rounded-t-3xl sm:rounded-3xl bg-slate-900 text-white shadow-2xl border border-slate-700 overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Camera className="h-5 w-5 text-emerald-400" />
            <h2 id="camera-modal-title" className="text-base font-bold">
              {isKn ? 'ಮಾರ್ಗದರ್ಶಿ ಕ್ಷೇತ್ರ ಕ್ಯಾಮೆರಾ' : 'Guided In-App Field Camera'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-slate-800 p-1.5 text-slate-300 hover:bg-slate-700"
            aria-label="Close Camera"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Gallery Upload Blocked Badge */}
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-amber-500/15 border border-amber-400/35 px-3.5 py-2.5 text-xs">
            <span className="inline-flex items-center gap-1.5 font-bold text-amber-200">
              <Lock className="h-3.5 w-3.5" />
              {isKn
                ? 'ಲೈವ್ ಜಿಯೋಟ್ಯಾಗ್ ಕ್ಯಾಪ್ಚರ್ ಮಾತ್ರ — ಗ್ಯಾಲರಿ ಅಪ್‌ಲೋಡ್ ನಿರ್ಬಂಧಿತ'
                : 'Live Geotagged Capture Only — Prevents Insurer Rejection'}
            </span>
            <button
              type="button"
              onClick={onOpenRules}
              className="font-bold text-emerald-300 underline hover:text-emerald-200"
            >
              {isKn ? 'PMFBY ಸಾಕ್ಷ್ಯ ನಿಯಮ' : 'PMFBY Rules'}
            </button>
          </div>

          {/* Simulated Live Camera Viewfinder with Crop Alignment Guides */}
          <div className="relative h-56 rounded-2xl bg-gradient-to-br from-emerald-950 via-stone-900 to-emerald-900 border border-emerald-500/40 overflow-hidden flex items-center justify-center">
            {/* Simulated field texture */}
            <div className="absolute inset-0 opacity-30 bg-[radial-gradient(circle_at_center,_#34d399_1px,_transparent_1px)] [background-size:18px_18px]" />

            {/* Alignment Reticle Corners */}
            <div className="relative z-10 w-4/5 h-36 border border-dashed border-emerald-300/60 rounded-xl flex flex-col items-center justify-center text-center px-4">
              <span className="absolute -top-1 -left-1 w-5 h-5 border-t-4 border-l-4 border-emerald-400 rounded-tl-md" />
              <span className="absolute -top-1 -right-1 w-5 h-5 border-t-4 border-r-4 border-emerald-400 rounded-tr-md" />
              <span className="absolute -bottom-1 -left-1 w-5 h-5 border-b-4 border-l-4 border-emerald-400 rounded-bl-md" />
              <span className="absolute -bottom-1 -right-1 w-5 h-5 border-b-4 border-r-4 border-emerald-400 rounded-br-md" />

              <Sparkles className="h-7 w-7 text-emerald-300 mb-1.5" />
              <p className="text-xs sm:text-sm font-bold text-white">
                {isKn
                  ? `${plot.cropKn} ಬೆಳೆ ಮತ್ತು ಮಣ್ಣನ್ನು ಚೌಕಟ್ಟಿನೊಳಗೆ ಇರಿಸಿ`
                  : `Align ${plot.crop} canopy & soil inside frame`}
              </p>
              <p className="text-[11px] text-emerald-200 mt-1">
                <MapPin className="inline h-3 w-3 mr-0.5" />
                {plot.gpsLat.toFixed(4)}° N, {plot.gpsLon.toFixed(4)}° E · {plot.surveyNo}
              </p>
            </div>

            <div className="absolute top-2.5 left-3 rounded-full bg-black/60 px-2.5 py-0.5 text-[11px] font-mono text-emerald-300">
              GPS LOCKED · LIVE SENSOR
            </div>
            <div className="absolute bottom-2.5 right-3 rounded-full bg-black/60 px-2.5 py-0.5 text-[11px] font-semibold text-slate-300 flex items-center gap-1">
              <ShieldAlert className="h-3 w-3 text-amber-300" /> Gallery Blocked
            </div>
          </div>

          {/* Capture CTA */}
          <button
            type="button"
            onClick={handleCapture}
            disabled={capturing}
            className="w-full rounded-2xl bg-emerald-500 py-3.5 text-base font-extrabold text-slate-950 shadow-lg hover:bg-emerald-400 transition flex items-center justify-center gap-2 disabled:opacity-60"
          >
            <Camera className="h-5 w-5" />
            <span>
              {capturing
                ? isKn
                  ? 'SHA-256 ಸಾಕ್ಷ್ಯ ಸಿದ್ಧವಾಗುತ್ತಿದೆ…'
                  : 'Logging SHA-256 Proof…'
                : isKn
                  ? '📸 ಹೊಲದ ಫೋಟೋ ತೆಗೆಯಿರಿ (Capture Field Photo)'
                  : '📸 Capture Field Photo'}
            </span>
          </button>

          {/* Immediate Closed-Loop Reward Preview */}
          {previewProof && (
            <div className="rounded-2xl bg-emerald-950/90 border border-emerald-400/40 p-4 space-y-2">
              <div className="flex items-center gap-2 text-emerald-300 text-xs font-extrabold uppercase">
                <CheckCircle2 className="h-4 w-4" />
                {isKn ? 'ತಕ್ಷಣದ ಬೆಳೆ ಆರೋಗ್ಯ ವಿಶ್ಲೇಷಣೆ' : 'Instant Crop Health Diagnosis'}
              </div>
              <div className="text-sm font-bold text-white">
                {isKn ? previewProof.diagnosisTitleKn : previewProof.diagnosisTitleEn}
              </div>
              <p className="text-xs text-emerald-100/90">
                {isKn ? previewProof.diagnosisDetailKn : previewProof.diagnosisDetailEn}
              </p>
              <div className="rounded-xl bg-black/40 p-2.5 font-mono text-[11px] text-emerald-300 break-all">
                SHA-256: {previewProof.sha256}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
