import { RefreshCw, SlidersHorizontal, Wifi, WifiOff, X } from 'lucide-react';
import React, { useState } from 'react';
import type { Language, StressScenario } from '../types';

interface EvaluatorControlsProps {
  lang: Language;
  scenario: StressScenario;
  onChangeScenario: (s: StressScenario) => void;
  offlineMode: boolean;
  onToggleOffline: () => void;
  queuedCount: number;
  onSyncQueue: () => void;
  claimStage: number;
  onAdvanceStage: () => void;
  onResetStages: () => void;
}

export const EvaluatorControls: React.FC<EvaluatorControlsProps> = ({
  lang,
  scenario,
  onChangeScenario,
  offlineMode,
  onToggleOffline,
  queuedCount,
  onSyncQueue,
  claimStage,
  onAdvanceStage,
  onResetStages,
}) => {
  const [open, setOpen] = useState(false);
  const isKn = lang === 'kn';

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 shadow-xs hover:bg-slate-100"
      >
        <SlidersHorizontal className="h-3.5 w-3.5 text-emerald-700" />
        <span>{isKn ? 'ಮೌಲ್ಯಮಾಪಕ ಡೆಮೊ' : 'Evaluator Demo'}</span>
        {offlineMode && (
          <span className="h-2 w-2 rounded-full bg-amber-500" title="Offline Queue Active" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl z-40 text-left">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-800">
              Evaluator Demo Controls
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-full p-1 text-slate-500 hover:bg-slate-100"
              aria-label="Close Evaluator Demo Controls"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* (a) Stress Scenario */}
          <div className="mb-3">
            <div className="text-xs font-semibold text-slate-600 mb-1.5">
              (a) Satellite Moisture Scenario
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {(
                [
                  { id: 'normal', label: 'Normal Moisture (+0.14 NDMI)' },
                  { id: 'drought', label: 'Severe Drought (-0.18 NDMI)' },
                  { id: 'waterlogged', label: 'Severe Waterlogging (+0.42 NDMI)' },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onChangeScenario(opt.id)}
                  className={`rounded-xl px-3 py-2 text-xs font-bold text-left border transition ${
                    scenario === opt.id
                      ? 'bg-emerald-900 text-white border-emerald-900'
                      : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* (b) Offline Queue vs Online Sync */}
          <div className="mb-3 border-t border-slate-100 pt-3">
            <div className="text-xs font-semibold text-slate-600 mb-1.5">
              (b) Connectivity &amp; Offline Queue
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onToggleOffline}
                className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold border ${
                  offlineMode
                    ? 'bg-amber-100 text-amber-900 border-amber-300'
                    : 'bg-emerald-50 text-emerald-900 border-emerald-200'
                }`}
              >
                {offlineMode ? <WifiOff className="h-3.5 w-3.5" /> : <Wifi className="h-3.5 w-3.5" />}
                {offlineMode ? `Offline Queue (${queuedCount})` : 'Online Sync'}
              </button>
              {queuedCount > 0 && (
                <button
                  type="button"
                  onClick={onSyncQueue}
                  className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800"
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Sync
                </button>
              )}
            </div>
          </div>

          {/* (c) Advance 5-Stage Claim Tracker */}
          <div className="border-t border-slate-100 pt-3">
            <div className="text-xs font-semibold text-slate-600 mb-1.5">
              (c) Live 5-Stage Claim Tracker (Stage {claimStage}/5)
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onAdvanceStage}
                disabled={claimStage >= 5}
                className="flex-1 rounded-xl bg-emerald-700 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-800 disabled:opacity-40"
              >
                Advance Stage →
              </button>
              <button
                type="button"
                onClick={onResetStages}
                className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
              >
                Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
