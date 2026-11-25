import { Droplets, Pause, Satellite, Volume2 } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import type { Language, PlotRecord, ScenarioTelemetry } from '../types';

interface AdvisoryCardProps {
  plot: PlotRecord;
  telemetry: ScenarioTelemetry;
  lang: Language;
}

export const AdvisoryCard: React.FC<AdvisoryCardProps> = ({ plot, telemetry, lang }) => {
  const [playing, setPlaying] = useState(false);
  const isKn = lang === 'kn';

  useEffect(() => {
    setPlaying(false);
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }, [telemetry.id, plot.id]);

  const togglePlay = () => {
    if (playing) {
      setPlaying(false);
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      return;
    }
    setPlaying(true);
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(telemetry.kannadaTranscript);
      utter.lang = 'kn-IN';
      utter.rate = 0.92;
      utter.onend = () => setPlaying(false);
      utter.onerror = () => setPlaying(false);
      window.speechSynthesis.speak(utter);
    } else {
      setTimeout(() => setPlaying(false), 5000);
    }
  };

  const gaugeColor =
    telemetry.id === 'normal'
      ? 'bg-emerald-600'
      : telemetry.id === 'drought'
        ? 'bg-amber-600'
        : 'bg-sky-600';

  const bannerStyle =
    telemetry.id === 'normal'
      ? 'border-emerald-300 bg-emerald-50 text-emerald-950'
      : telemetry.id === 'drought'
        ? 'border-rose-300 bg-rose-50 text-rose-950'
        : 'border-sky-300 bg-sky-50 text-sky-950';

  return (
    <section
      className="rounded-3xl border-2 border-emerald-900/15 bg-white p-5 shadow-sm"
      aria-labelledby="advisory-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="rounded-2xl bg-sky-100 p-2.5 text-sky-800">
            <Droplets className="h-6 w-6" />
          </div>
          <div>
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-700">
              <Satellite className="h-3 w-3 text-sky-700" /> Sentinel-2 + FAO-56 ET₀
            </span>
            <h2 id="advisory-heading" className="text-lg font-extrabold text-slate-900 mt-1">
              {isKn
                ? '7-ದಿನದ ನೀರಾವರಿ ಸಲಹೆ (Daily Utility)'
                : '7-Day FAO-56 & Sentinel-2 Advisory'}
            </h2>
          </div>
        </div>
      </div>

      {/* Soil Moisture Gauge */}
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 mb-4">
        <div className="flex items-center justify-between text-xs sm:text-sm font-bold text-slate-700 mb-2">
          <span>
            {isKn ? 'ಬೇರಿನ ವಲಯದ ಮಣ್ಣಿನ ತೇವಾಂಶ' : 'Root-Zone Soil Moisture'} (
            {telemetry.soilMoisturePct}%)
          </span>
          <span className="font-mono text-xs text-slate-600">
            NDMI: {telemetry.ndmi >= 0 ? `+${telemetry.ndmi.toFixed(2)}` : telemetry.ndmi.toFixed(2)} · ET₀:{' '}
            {telemetry.et0MmDay.toFixed(1)} mm/d
          </span>
        </div>
        <div className="h-4 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className={`h-full rounded-full transition-all duration-500 ${gaugeColor}`}
            style={{ width: `${Math.min(100, Math.max(8, telemetry.soilMoisturePct))}%` }}
          />
        </div>
        <div className="mt-1.5 flex justify-between text-[11px] font-semibold text-slate-500">
          <span>{isKn ? 'ಒಣ ಒತ್ತಡ (<25%)' : 'Dry Stress (<25%)'}</span>
          <span>{isKn ? 'ಸಮರ್ಪಕ (45–75%)' : 'Optimal (45–75%)'}</span>
          <span>{isKn ? 'ಜಲಾವೃತ (>85%)' : 'Waterlogged (>85%)'}</span>
        </div>
      </div>

      {/* Plain-Language Kannada + English Action Banner */}
      <div className={`rounded-2xl border-2 p-4 mb-4 ${bannerStyle}`}>
        <div className="text-sm sm:text-base font-extrabold leading-snug">
          {telemetry.actionKn}
        </div>
        <div className="text-xs sm:text-sm font-medium opacity-85 mt-1.5">
          {telemetry.actionEn}
        </div>
      </div>

      {/* Kannada Audio Playback Simulator + Waveform + Transcript */}
      <div className="rounded-2xl border border-emerald-200 bg-emerald-950 p-4 text-white">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <button
            type="button"
            onClick={togglePlay}
            className="inline-flex items-center gap-2 rounded-full bg-emerald-400 px-4 py-2.5 text-sm font-extrabold text-emerald-950 shadow-sm hover:bg-emerald-300 transition"
          >
            {playing ? <Pause className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
            <span>
              {playing
                ? isKn
                  ? 'ನಿಲ್ಲಿಸಿ (Pause)'
                  : 'Pause Kannada Audio'
                : 'ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ · Listen in Kannada'}
            </span>
          </button>

          {/* Animated Waveform */}
          <div className="flex items-center gap-1 h-7" aria-hidden="true">
            {[0.4, 0.8, 0.6, 1, 0.5, 0.9, 0.7, 0.4, 0.85, 0.55].map((h, i) => (
              <span
                key={i}
                className={`w-1 rounded-full bg-emerald-300 ${playing ? 'waveform-bar' : ''}`}
                style={{
                  height: playing ? '24px' : `${Math.round(h * 14)}px`,
                  animationDelay: `${i * 0.09}s`,
                  opacity: playing ? 1 : 0.45,
                }}
              />
            ))}
          </div>
        </div>

        <p className="text-xs sm:text-sm leading-relaxed text-emerald-100 bg-white/10 rounded-xl p-3">
          “{telemetry.kannadaTranscript}”
        </p>
      </div>
    </section>
  );
};
