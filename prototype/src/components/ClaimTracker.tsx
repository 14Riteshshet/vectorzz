import {
  CheckCircle2,
  Clock,
  HelpCircle,
  Mic,
  Satellite,
  ShieldCheck,
} from 'lucide-react';
import React from 'react';
import type {
  CapturedPhotoProof,
  Language,
  PlotRecord,
  ScenarioTelemetry,
} from '../types';

interface ClaimTrackerProps {
  lang: Language;
  plot: PlotRecord;
  telemetry: ScenarioTelemetry;
  proof: CapturedPhotoProof | null;
  claimStage: number;
  voiceLossLogged: boolean;
  onLogVoiceLoss: () => void;
  onOpenRules: () => void;
}

export const ClaimTracker: React.FC<ClaimTrackerProps> = ({
  lang,
  plot,
  telemetry,
  proof,
  claimStage,
  voiceLossLogged,
  onLogVoiceLoss,
  onOpenRules,
}) => {
  const isKn = lang === 'kn';
  const active = telemetry.thresholdCrossed || voiceLossLogged || Boolean(proof);
  const effectiveStage = active ? Math.max(2, claimStage) : 0;

  const stages = [
    {
      num: 1,
      titleEn: 'Geotagged Photo & SHA-256 Logged',
      titleKn: 'ಜಿಯೋಟ್ಯಾಗ್ ಫೋಟೋ ಮತ್ತು SHA-256 ದಾಖಲಾಗಿದೆ',
      subEn: proof
        ? `SHA-256: ${proof.sha256.slice(0, 14)}… · ${proof.lat.toFixed(4)}° N, ${proof.lon.toFixed(4)}° E`
        : `Parcel GPS locked (${plot.gpsLat.toFixed(4)}° N, ${plot.gpsLon.toFixed(4)}° E)`,
      subKn: proof
        ? `SHA-256: ${proof.sha256.slice(0, 14)}… · ಜಿಯೋಟ್ಯಾಗ್ ದೃಢೀಕೃತ`
        : `ಜಮೀನಿನ GPS (${plot.gpsLat.toFixed(4)}° N, ${plot.gpsLon.toFixed(4)}° E) ಲಾಕ್ ಆಗಿದೆ`,
      time: '10:12 AM',
    },
    {
      num: 2,
      titleEn: 'Sentinel-2 NDMI & Weather Cross-Check',
      titleKn: 'Sentinel-2 NDMI ಮತ್ತು ಹವಾಮಾನ ಪರಿಶೀಲನೆ',
      subEn: '30% YES-TECH Satellite Weightage Verified · FAO-56 deficit matched',
      subKn: '30% YES-TECH ಉಪಗ್ರಹ ತೂಕ ದೃಢೀಕೃತ · FAO-56 ನೀರಿನ ಕೊರತೆ ಪರಿಶೀಲಿತ',
      time: '10:14 AM',
    },
    {
      num: 3,
      titleEn: 'Block Level CCE / Assessor Sync',
      titleKn: 'ಹೋಬಳಿ/ತಾಲ್ಲೂಕು ಮಟ್ಟದ CCE / ಅಧಿಕಾರಿ ಸಿಂಕ್',
      subEn: `${plot.blockOfficer} synced`,
      subKn: `${plot.blockOfficer} ಪರಿಶೀಲನೆ`,
      time: 'In Progress',
    },
    {
      num: 4,
      titleEn: 'AIC Insurer Automated Audit',
      titleKn: 'AIC ವಿಮಾ ಕಂಪನಿ ಸ್ವಯಂಚಾಲಿತ ಲೆಕ್ಕಪರಿಶೋಧನೆ',
      subEn: 'Target SLA: 48 Hours · Zero manual paper chase',
      subKn: 'ಗುರಿ SLA: 48 ಗಂಟೆಗಳು · ಕಾಗದ ರಹಿತ ಪರಿಶೀಲನೆ',
      time: 'SLA: 48 Hrs',
    },
    {
      num: 5,
      titleEn: 'Direct Benefit Transfer (DBT) to Bank Account',
      titleKn: 'ಬ್ಯಾಂಕ್ ಖಾತೆಗೆ ನೇರ ಪರಿಹಾರ ಜಮೆ (DBT)',
      subEn: `Exact payout ₹${(telemetry.payoutInr || 45000).toLocaleString('en-IN')} queued to Aadhaar-seeded bank`,
      subKn: `₹${(telemetry.payoutInr || 45000).toLocaleString('en-IN')} ಪರಿಹಾರ ಆಧಾರ್-ಲಿಂಕ್ ಬ್ಯಾಂಕ್ ಖಾತೆಗೆ ಸಿದ್ಧ`,
      time: 'Queued',
    },
  ];

  return (
    <section
      className="rounded-3xl border-2 border-emerald-900/15 bg-white p-5 shadow-sm"
      aria-labelledby="claim-tracker-heading"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="rounded-2xl bg-emerald-100 p-2.5 text-emerald-800">
            <Satellite className="h-6 w-6" />
          </div>
          <div>
            <h2 id="claim-tracker-heading" className="text-lg font-extrabold text-slate-900">
              {isKn
                ? '5-ಹಂತದ ನೇರ ದಾವೆ ಮತ್ತು ಪರಿಶೀಲನಾ ಟ್ರ್ಯಾಕರ್'
                : '5-Stage Live Claim & Verification Tracker'}
            </h2>
            <p className="text-xs text-slate-500">
              {isKn
                ? 'ಪಾರದರ್ಶಕ ನೇರ ಸ್ಥಿತಿ — "Under Review" ಅಸ್ಪಷ್ಟತೆ ಇಲ್ಲ'
                : 'Live operational pipeline — no black-box "Under Review" delays'}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenRules}
          className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1.5 text-xs font-bold text-emerald-800 hover:bg-emerald-100"
        >
          <HelpCircle className="h-3.5 w-3.5" />
          {isKn ? 'PMFBY ನಿಯಮ' : 'PMFBY Rules'}
        </button>
      </div>

      {!active ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-center space-y-3">
          <p className="text-sm text-slate-700 font-medium">
            {isKn
              ? 'ಪ್ರಸ್ತುತ ಬೆಳೆ ಆರೋಗ್ಯಕರವಾಗಿದೆ. ಬರ/ಜಲಾವೃತ ಒತ್ತಡ ಕಂಡುಬಂದಲ್ಲಿ ಅಥವಾ ಧ್ವನಿ ವರದಿ ಸಲ್ಲಿಸಿದಾಗ 5-ಹಂತದ ದಾವೆ ಟ್ರ್ಯಾಕರ್ ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಆರಂಭವಾಗುತ್ತದೆ.'
              : 'Plot moisture is currently healthy. Switch to a stress scenario in Evaluator Demo or log a localized crop-loss voice note below to trigger the 5-stage tracker.'}
          </p>
          <button
            type="button"
            onClick={onLogVoiceLoss}
            className="inline-flex items-center gap-2 rounded-full bg-amber-500 px-5 py-2.5 text-sm font-extrabold text-slate-950 shadow-xs hover:bg-amber-400 transition"
          >
            <Mic className="h-4 w-4" />
            {isKn
              ? 'ಧ್ವನಿ ಮೂಲಕ ಬೆಳೆ ನಷ್ಟ ವರದಿ ಮಾಡಿ (Log Loss via Voice)'
              : 'Log Crop Loss via Voice Note'}
          </button>
        </div>
      ) : (
        <ol className="relative space-y-4 border-l-2 border-emerald-200 ml-3 pl-5">
          {stages.map((st) => {
            const done = effectiveStage >= st.num;
            const current = effectiveStage + 1 === st.num;
            return (
              <li key={st.num} className="relative">
                <span
                  className={`absolute -left-[29px] top-0.5 flex h-6 w-6 items-center justify-center rounded-full border-2 ${
                    done
                      ? 'bg-emerald-600 border-emerald-600 text-white'
                      : current
                        ? 'bg-amber-100 border-amber-500 text-amber-700'
                        : 'bg-white border-slate-300 text-slate-400'
                  }`}
                >
                  {done ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : current ? (
                    <Clock className="h-3.5 w-3.5" />
                  ) : (
                    <ShieldCheck className="h-3.5 w-3.5" />
                  )}
                </span>
                <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span
                      className={`text-sm font-extrabold ${
                        done ? 'text-emerald-950' : current ? 'text-amber-900' : 'text-slate-500'
                      }`}
                    >
                      {st.num}. {isKn ? st.titleKn : st.titleEn}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${
                        done
                          ? 'bg-emerald-100 text-emerald-800'
                          : current
                            ? 'bg-amber-100 text-amber-900'
                            : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {done ? (isKn ? 'ಪೂರ್ಣಗೊಂಡಿದೆ' : 'Completed') : st.time}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 mt-1">
                    {isKn ? st.subKn : st.subEn}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
};
