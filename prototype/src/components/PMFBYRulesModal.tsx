import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  PhoneCall,
  ShieldCheck,
  X,
} from 'lucide-react';
import React from 'react';
import type { CapturedPhotoProof, CultivatorStatus, Language, PlotRecord } from '../types';

interface PMFBYRulesModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  plot: PlotRecord | null;
  cultivatorStatus: CultivatorStatus;
  consentGiven: boolean;
  capturedProof: CapturedPhotoProof | null;
}

export const PMFBYRulesModal: React.FC<PMFBYRulesModalProps> = ({
  isOpen,
  onClose,
  lang,
  plot,
  cultivatorStatus,
  consentGiven,
  capturedProof,
}) => {
  if (!isOpen) return null;

  const isKn = lang === 'kn';

  const checklist = [
    {
      ok: Boolean(plot),
      labelEn: 'Notified Land & Survey/ULPIN Matched (Gubbi / Koratagere, Tumakuru)',
      labelKn: 'ಅಧಿಸೂಚಿತ ಜಮೀನು ಮತ್ತು ಸರ್ವೆ/ULPIN ಸಂಖ್ಯೆ ದೃಢೀಕೃತ (ತುಮಕೂರು)',
    },
    {
      ok: cultivatorStatus === 'landowner' || consentGiven,
      labelEn:
        cultivatorStatus === 'tenant'
          ? 'Tenant / Sharecropper Declaration & Tenancy Proof Noted (Eligible under PMFBY)'
          : 'Landowner (Khatedar) RTC / Pahani Record Linked',
      labelKn:
        cultivatorStatus === 'tenant'
          ? 'ಗೇಣಿದಾರ / ಪಾಲುದಾರ ಘೋಷಣೆ ಮತ್ತು ಗೇಣಿ ದಾಖಲೆ ಗುರುತಿಸಲಾಗಿದೆ (PMFBY ಅರ್ಹರು)'
          : 'ಖಾತೆದಾರರ RTC / ಪಹಣಿ ದಾಖಲೆ ಲಿಂಕ್ ಆಗಿದೆ',
    },
    {
      ok: Boolean(plot?.aadhaarBankLinked && consentGiven),
      labelEn: 'AgriStack Consent & Aadhaar-Seeded DBT Bank Account Ready',
      labelKn: 'AgriStack ಒಪ್ಪಿಗೆ ಮತ್ತು ಆಧಾರ್-ಲಿಂಕ್ ಬ್ಯಾಂಕ್ ಖಾತೆ ಸಿದ್ಧವಾಗಿದೆ',
    },
    {
      ok: Boolean(capturedProof),
      labelEn: 'Live Geotagged Field Evidence (SHA-256) Captured Within 72-Hr Window',
      labelKn: '72 ಗಂಟೆಯೊಳಗೆ ಲೈವ್ ಜಿಯೋಟ್ಯಾಗ್ ಕ್ಷೇತ್ರ ಫೋಟೋ (SHA-256) ದಾಖಲಾಗಿದೆ',
    },
  ];

  const readyCount = checklist.filter((c) => c.ok).length;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-900/60 backdrop-blur-xs p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pmfby-rules-title"
    >
      <div className="w-full max-w-2xl max-h-[92vh] overflow-y-auto rounded-t-3xl sm:rounded-3xl bg-white shadow-2xl border border-emerald-900/10">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between gap-3 bg-emerald-900 px-5 py-4 text-white">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-6 w-6 text-emerald-300 shrink-0" />
            <div>
              <h2 id="pmfby-rules-title" className="text-base sm:text-lg font-bold leading-snug">
                {isKn
                  ? 'PMFBY ನಿಯಮಗಳು, ಅರ್ಹತೆ ಮತ್ತು ವಿಶ್ವಾಸಾರ್ಹ ಮಾರ್ಗದರ್ಶಿ'
                  : 'PMFBY Rules, Eligibility & Trust Guide'}
              </h2>
              <p className="text-xs text-emerald-200">
                {isKn
                  ? 'ಪ್ರಧಾನ ಮಂತ್ರಿ ಫಸಲ್ ಬಿಮಾ ಯೋಜನೆ · ಪಾರದರ್ಶಕ ಮಾಹಿತಿ'
                  : 'Pradhan Mantri Fasal Bima Yojana · Plain-Language Farmer Guide'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-white/15 p-2 text-white hover:bg-white/25 transition"
            aria-label="Close PMFBY Rules Guide"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 p-5 text-sm sm:text-base text-slate-800">
          {/* Interactive Live Eligibility Checklist */}
          <section className="rounded-2xl border-2 border-emerald-200 bg-emerald-50/70 p-4">
            <div className="flex items-center justify-between gap-2 mb-3">
              <h3 className="font-bold text-emerald-950">
                {isKn
                  ? 'ನೇರ ಅರ್ಹತಾ ಪರಿಶೀಲನಾ ಪಟ್ಟಿ (Live Checklist)'
                  : 'Live PMFBY Readiness Checklist'}
              </h3>
              <span className="rounded-full bg-emerald-700 px-3 py-0.5 text-xs font-bold text-white">
                {readyCount}/{checklist.length} {isKn ? 'ಪೂರ್ಣ' : 'Ready'}
              </span>
            </div>
            <ul className="space-y-2">
              {checklist.map((item, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2.5 rounded-xl bg-white p-2.5 border border-emerald-100"
                >
                  {item.ok ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                  )}
                  <span className={item.ok ? 'text-slate-900 font-medium' : 'text-slate-600'}>
                    {isKn ? item.labelKn : item.labelEn}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {/* 1. Who Is Eligible */}
          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 className="font-bold text-slate-900 mb-1.5">
              1. {isKn ? 'ಯಾರು ಅರ್ಹರು? (Who Is Eligible)' : 'Who Is Eligible'}
            </h3>
            <p className="text-slate-700 leading-relaxed">
              {isKn
                ? 'ಅಧಿಸೂಚಿತ ಪ್ರದೇಶಗಳಲ್ಲಿ (ಉದಾ: ಗುಬ್ಬಿ, ಕೊರಟಗೆರೆ) ಅಧಿಸೂಚಿತ ಬೆಳೆಗಳನ್ನು (ರಾಗಿ, ಶೇಂಗಾ, ಅಡಿಕೆ) ಬೆಳೆಯುವ ಭೂಮಾಲೀಕರು (ಖಾತೆದಾರರು), ಗೇಣಿದಾರರು ಮತ್ತು ಪಾಲುದಾರ ರೈತರು ಕಟ್-ಆಫ್ ದಿನಾಂಕದೊಳಗೆ ನೋಂದಾಯಿಸಿದರೆ ಅರ್ಹರಾಗಿರುತ್ತಾರೆ. ಸರಿಯಾದ ಸರ್ವೆ ಸಂಖ್ಯೆ, ಬೆಳೆ ವಿವರ ಮತ್ತು ಆಧಾರ್-ಲಿಂಕ್ ಬ್ಯಾಂಕ್ ಖಾತೆ ಅಗತ್ಯ.'
                : 'Landowners (Khatedars), tenant farmers, and sharecroppers cultivating notified crops in notified insurance units before cut-off dates are eligible. Matching land/survey details (or valid tenancy proof), accurate crop records, and an Aadhaar-seeded bank account are required.'}
            </p>
          </section>

          {/* 2. How Payouts Are Calculated */}
          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 className="font-bold text-slate-900 mb-1.5">
              2. {isKn ? 'ಪರಿಹಾರ ಹೇಗೆ ಲೆಕ್ಕಹಾಕಲಾಗುತ್ತದೆ? (Payout Calculation)' : 'How Payouts Are Calculated'}
            </h3>
            <p className="text-slate-700 leading-relaxed">
              {isKn
                ? 'ವಿಮಾ ಮೊತ್ತ = ಸ್ಕೇಲ್ ಆಫ್ ಫೈನಾನ್ಸ್ × ವಿಸ್ತೀರ್ಣ (2.5 ಎಕರೆಗೆ ₹1,12,500). ರೈತರ ಪಾಲು ಖಾರಿಫ್‌ಗೆ ಗರಿಷ್ಠ 2% (₹2,250), ರಬಿಗೆ 1.5%, ವಾಣಿಜ್ಯ/ತೋಟಗಾರಿಕೆಗೆ 5% ಮಾತ್ರ; ಉಳಿದ ₹9,000+ ಪ್ರೀಮಿಯಂ ಅನ್ನು ಕೇಂದ್ರ ಮತ್ತು ರಾಜ್ಯ ಸರ್ಕಾರಗಳು ಭರಿಸುತ್ತವೆ. ಇಳುವರಿ ಕೊರತೆ ಅಥವಾ ಸ್ಥಳೀಯ ವಿಪತ್ತು ದೃಢಪಟ್ಟಾಗ ನೇರವಾಗಿ ಬ್ಯಾಂಕ್ ಖಾತೆಗೆ (DBT) ಪರಿಹಾರ ಜಮೆಯಾಗುತ್ತದೆ.'
                : 'Sum Insured equals Scale of Finance × Insured Area (e.g., ₹1,12,500 for 2.5 acres). Farmers pay capped premiums of 2% (Kharif, ₹2,250), 1.5% (Rabi), or up to 5% (commercial/horticultural), while Central & State Governments subsidize the remaining ₹9,000+. Yield shortfall (with 30% YES-TECH satellite weightage) or verified localized peril triggers DBT bank payouts.'}
            </p>
          </section>

          {/* 3. Covered vs Excluded */}
          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h3 className="font-bold text-slate-900 mb-1.5">
              3. {isKn ? 'ವಿಮೆ ವ್ಯಾಪ್ತಿ ಮತ್ತು ತಿರಸ್ಕಾರಕ್ಕೆ ಕಾರಣಗಳು' : 'Covered vs. Excluded & Rejection Triggers'}
            </h3>
            <div className="grid sm:grid-cols-2 gap-3 mt-2 text-xs sm:text-sm">
              <div className="rounded-xl bg-emerald-50 p-3 border border-emerald-200">
                <div className="font-bold text-emerald-900 mb-1">
                  {isKn ? '✅ ವ್ಯಾಪ್ತಿಗೆ ಒಳಪಡುವ ನಷ್ಟಗಳು' : '✅ Covered Non-Preventable Perils'}
                </div>
                <p className="text-emerald-900/90">
                  {isKn
                    ? 'ಬರ, ಒಣಹವೆ, ಅತಿವೃಷ್ಟಿ, ಜಲಾವೃತ, ಆಲಿಕಲ್ಲು, ಭೂಕುಸಿತ, ಮತ್ತು ಕಟಾವು ನಂತರದ 14 ದಿನದೊಳಗಿನ ಚಂಡಮಾರುತ/ಮಳೆ ನಷ್ಟ.'
                    : 'Drought, dry spells, flood, inundation, hailstorm, landslide, and post-harvest cyclonic/unseasonal rain within 14 days.'}
                </p>
              </div>
              <div className="rounded-xl bg-rose-50 p-3 border border-rose-200">
                <div className="font-bold text-rose-900 mb-1">
                  {isKn ? '❌ ತಿರಸ್ಕಾರಕ್ಕೆ ಸಾಮಾನ್ಯ ಕಾರಣಗಳು' : '❌ Exclusions & Rejection Triggers'}
                </div>
                <p className="text-rose-900/90">
                  {isKn
                    ? 'ತಡೆಗಟ್ಟಬಹುದಾದ ನಿರ್ಲಕ್ಷ್ಯ, ಅಧಿಸೂಚಿಸದ ಬೆಳೆ, ಸರ್ವೆ/ವಿಸ್ತೀರ್ಣ ವ್ಯತ್ಯಾಸ, ಸ್ಥಳೀಯ ನಷ್ಟಕ್ಕೆ 72 ಗಂಟೆಯೊಳಗೆ ವರದಿ ಮಾಡದಿರುವುದು, ಅಥವಾ ಬ್ಯಾಂಕ್ ಖಾತೆ ಸಮಸ್ಯೆ.'
                    : 'Preventable negligence, unnotified crops/areas, crop/survey area mismatch, missing the 72-hour localized loss reporting window, or inactive bank DBT.'}
                </p>
              </div>
            </div>
          </section>

          {/* 4. Trust Disclosure */}
          <section className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="font-bold text-slate-900 mb-1.5">
              4. {isKn ? 'ಈ ಸಾಧನವನ್ನು ಹೇಗೆ ನಂಬಬಹುದು?' : 'How You Can Trust This Tool'}
            </h3>
            <p className="text-slate-700 leading-relaxed mb-3">
              {isKn
                ? 'SookshmaJal ಅಧಿಕೃತ PMFBY ಪೋರ್ಟಲ್ (pmfby.gov.in) ಮತ್ತು ಕೃಷಿ ಮಿತ್ರ (14447) ಜೊತೆಗೆ ರೈತರಿಗೆ ನೀರಾವರಿ ಸಲಹೆ ಹಾಗೂ ಬದಲಾಯಿಸಲಾಗದ (SHA-256) ಕ್ಷೇತ್ರ ಸಾಕ್ಷ್ಯವನ್ನು ಸಿದ್ಧಪಡಿಸಲು ಸಹಾಯ ಮಾಡುತ್ತದೆ.'
                : 'SookshmaJal assists farmers with daily FAO-56 irrigation coaching and tamper-evident SHA-256 field evidence logs alongside official PMFBY portals (pmfby.gov.in) and Krishi Mitra (14447).'}
            </p>
            <div className="flex flex-wrap gap-2.5">
              <a
                href="https://pmfby.gov.in"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-full bg-white px-3.5 py-2 text-xs font-bold text-emerald-800 border border-emerald-300 hover:bg-emerald-50"
              >
                <ExternalLink className="h-3.5 w-3.5" /> pmfby.gov.in
              </a>
              <a
                href="tel:14447"
                className="inline-flex items-center gap-1.5 rounded-full bg-emerald-800 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-900"
              >
                <PhoneCall className="h-3.5 w-3.5" /> {isKn ? 'ಕೃಷಿ ಮಿತ್ರ 14447' : 'Krishi Mitra 14447'}
              </a>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
