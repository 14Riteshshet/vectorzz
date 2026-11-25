import { Building2, HelpCircle, PhoneCall, ShieldCheck, UserCheck } from 'lucide-react';
import React from 'react';
import type { Language, PlotRecord } from '../types';

interface MoneyMapCardProps {
  plot: PlotRecord;
  lang: Language;
  onOpenRules: () => void;
}

export const MoneyMapCard: React.FC<MoneyMapCardProps> = ({ plot, lang, onOpenRules }) => {
  const isKn = lang === 'kn';

  return (
    <section
      className="rounded-3xl border-2 border-emerald-900/15 bg-white p-5 shadow-sm"
      aria-labelledby="money-map-heading"
    >
      <div className="flex flex-wrap items-start justify-between gap-2 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="rounded-2xl bg-emerald-100 p-2.5 text-emerald-800">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-900 px-2.5 py-0.5 text-[11px] font-bold text-emerald-100">
              <Building2 className="h-3 w-3" /> {plot.insurerShort}
            </span>
            <h2 id="money-map-heading" className="text-lg font-extrabold text-slate-900 mt-1">
              {isKn ? 'ಹಣಕಾಸು ನಕ್ಷೆ (Money Map)' : 'The Money Map — Upfront Clarity'}
            </h2>
          </div>
        </div>
        <span className="rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-bold text-emerald-800">
          {isKn ? 'ಯಾವುದೇ ಗುಪ್ತ ಶುಲ್ಕವಿಲ್ಲ' : 'No hidden fees'}
        </span>
      </div>

      {/* Exact Sum Insured */}
      <div className="rounded-2xl bg-gradient-to-br from-emerald-900 to-emerald-800 p-4 text-white mb-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-emerald-200">
          {isKn
            ? `ನಿಮ್ಮ ${plot.areaAcres} ಎಕರೆ ${plot.cropKn} ಬೆಳೆಗೆ ವಿಮಾ ರಕ್ಷಣೆ (Sum Insured)`
            : `Exact Sum Insured for ${plot.areaAcres} Acres (${plot.crop})`}
        </div>
        <div className="text-3xl font-extrabold tracking-tight mt-1">
          ₹{plot.sumInsuredInr.toLocaleString('en-IN')}
        </div>
        <div className="text-xs text-emerald-100 mt-1">
          {plot.insurerName} · {plot.notifiedSeason}
        </div>
      </div>

      {/* Cost Breakdown */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3.5">
          <div className="text-xs font-semibold text-slate-600">
            {isKn ? 'ರೈತರ ಪಾಲು (2% ಖಾರಿಫ್)' : 'Farmer Share (2% Kharif)'}
          </div>
          <div className="text-xl font-extrabold text-slate-900 mt-0.5">
            ₹{plot.farmerPremiumInr.toLocaleString('en-IN')}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">
            {isKn ? 'ಸರ್ಕಾರಿ ಮಿತ ದರ' : 'Capped govt rate'}
          </div>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-3.5">
          <div className="text-xs font-semibold text-emerald-800">
            {isKn ? 'ಸರ್ಕಾರದ ಸಬ್ಸಿಡಿ (80%)' : 'Govt Subsidy Share'}
          </div>
          <div className="text-xl font-extrabold text-emerald-900 mt-0.5">
            ₹{plot.govtSubsidyInr.toLocaleString('en-IN')}
          </div>
          <div className="text-[11px] text-emerald-700 mt-0.5">
            {isKn ? 'ಕೇಂದ್ರ + ರಾಜ್ಯ ಸರ್ಕಾರ' : 'Central + State Govt'}
          </div>
        </div>
      </div>

      {/* Concise Payout Rule + Inline Rules Link */}
      <div className="rounded-2xl bg-stone-50 border border-stone-200 p-3.5 text-xs sm:text-sm text-slate-700 mb-4">
        <p className="leading-relaxed">
          {isKn
            ? 'ಪರಿಹಾರ ಲೆಕ್ಕಾಚಾರ: ಸ್ಕೇಲ್ ಆಫ್ ಫೈನಾನ್ಸ್ × ಎಕರೆ ಆಧಾರದ ಮೇಲೆ ವಿಮಾ ಮೊತ್ತ ನಿಗದಿಯಾಗುತ್ತದೆ. 30% YES-TECH ಉಪಗ್ರಹ ತೂಕದೊಂದಿಗೆ ಇಳುವರಿ ಕೊರತೆ ಅಥವಾ ದೃಢೀಕೃತ ವಿಪತ್ತು ನಷ್ಟಕ್ಕೆ ನೇರ ಬ್ಯಾಂಕ್ (DBT) ಪಾವತಿ.'
            : 'Payout Rule: Sum Insured = Scale of Finance × Area. Yield shortfall (with 30% YES-TECH satellite weightage) or verified localized peril pays directly to your Aadhaar-linked bank (DBT).'}
        </p>
        <button
          type="button"
          onClick={onOpenRules}
          className="mt-2 inline-flex items-center gap-1.5 font-bold text-emerald-800 underline underline-offset-2 hover:text-emerald-950"
        >
          <HelpCircle className="h-4 w-4" />
          {isKn
            ? 'PMFBY ಅರ್ಹತೆ ಮತ್ತು ನಿಯಮಗಳನ್ನು ಪರಿಶೀಲಿಸಿ →'
            : 'Check PMFBY Eligibility & Rules →'}
        </button>
      </div>

      {/* Direct Claim Helpline & Block Officer Contact */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 text-xs">
        <div className="flex items-center gap-1.5 text-slate-700">
          <UserCheck className="h-4 w-4 text-emerald-700 shrink-0" />
          <span className="font-semibold">{plot.blockOfficer}</span>
        </div>
        <a
          href="tel:14447"
          className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 font-bold text-emerald-900 hover:bg-emerald-200"
        >
          <PhoneCall className="h-3.5 w-3.5" />
          {isKn ? 'ದಾವೆ ಸಹಾಯವಾಣಿ: 14447' : 'Claim Helpline: 14447'}
        </a>
      </div>
    </section>
  );
};
