import { Check, Copy, QrCode, Share2, ShieldCheck, X } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import type { CapturedPhotoProof, Language, PlotRecord } from '../types';

interface WhatsAppReceiptProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  plot: PlotRecord;
  proof: CapturedPhotoProof | null;
}

export const WhatsAppReceipt: React.FC<WhatsAppReceiptProps> = ({
  isOpen,
  onClose,
  lang,
  plot,
  proof,
}) => {
  const [copied, setCopied] = useState(false);

  const qrCells = useMemo(() => {
    const seed = proof?.sha256 || 'sookshmajal';
    const cells: boolean[] = [];
    for (let i = 0; i < 121; i++) {
      const ch = seed.charCodeAt(i % seed.length);
      cells.push(((ch + i * 7) % 3) !== 0);
    }
    return cells;
  }, [proof]);

  if (!isOpen || !proof) return null;
  const isKn = lang === 'kn';

  const shareText =
    `SookshmaJal PMFBY Verification Receipt\n` +
    `Farmer: ${plot.farmerName}\n` +
    `Plot: ${plot.surveyNo}, ${plot.taluk}, ${plot.district}\n` +
    `GPS: ${proof.lat.toFixed(4)}° N, ${proof.lon.toFixed(4)}° E\n` +
    `Timestamp: ${new Date(proof.timestampIso).toLocaleString('en-IN')}\n` +
    `SHA-256: ${proof.sha256}\n` +
    `Status: ${proof.synced ? 'Synced to AIC/PMFBY Audit Queue' : 'Saved in Offline Queue'}`;

  const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(shareText)}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-slate-900/65 backdrop-blur-xs p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="wa-receipt-title"
    >
      <div className="w-full max-w-md rounded-t-3xl sm:rounded-3xl bg-white shadow-2xl border border-emerald-200 overflow-hidden">
        <div className="flex items-center justify-between bg-emerald-800 px-5 py-4 text-white">
          <div className="flex items-center gap-2">
            <QrCode className="h-5 w-5 text-emerald-200" />
            <h2 id="wa-receipt-title" className="text-base font-bold">
              {isKn ? 'WhatsApp QR ಪರಿಶೀಲನಾ ರಸೀದಿ' : 'WhatsApp QR Verification Card'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-white/15 p-1.5 text-white hover:bg-white/25"
            aria-label="Close Receipt Modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Verified Confirmation */}
          <div className="rounded-2xl bg-emerald-50 border border-emerald-200 p-3 text-xs sm:text-sm text-emerald-950 font-semibold flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-emerald-700 shrink-0" />
            <span>
              {isKn
                ? 'ನಿಮ್ಮ ಹೊಲದ ಫೋಟೋ ಯಶಸ್ವಿಯಾಗಿ ದಾಖಲಾಗಿದೆ'
                : 'Field photo cryptographically anchored & ready for PMFBY audit'}
            </span>
          </div>

          {/* QR + Details */}
          <div className="flex flex-col items-center rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div
              className="grid grid-cols-11 gap-0.5 rounded-xl bg-white p-3 border border-slate-200 shadow-xs mb-3"
              aria-label="Verification QR Code"
            >
              {qrCells.map((on, idx) => (
                <span
                  key={idx}
                  className={`h-2.5 w-2.5 rounded-[1px] ${on ? 'bg-slate-900' : 'bg-white'}`}
                />
              ))}
            </div>
            <div className="text-center text-xs text-slate-700 space-y-1">
              <div className="font-bold text-slate-900">
                {plot.farmerName} · {plot.surveyNo}, {plot.taluk}
              </div>
              <div>
                GPS: {proof.lat.toFixed(4)}° N, {proof.lon.toFixed(4)}° E ·{' '}
                {new Date(proof.timestampIso).toLocaleTimeString('en-IN')}
              </div>
              <div className="font-mono text-[10px] text-emerald-800 bg-emerald-100/80 px-2.5 py-1 rounded-lg break-all">
                SHA-256: {proof.sha256}
              </div>
            </div>
          </div>

          {/* 1-Click Share to WhatsApp */}
          <div className="flex gap-2.5">
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noreferrer"
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-2xl bg-[#25D366] px-4 py-3 text-sm font-extrabold text-slate-950 shadow-sm hover:brightness-95 transition"
            >
              <Share2 className="h-4 w-4" />
              {isKn ? 'WhatsApp ನಲ್ಲಿ ಹಂಚಿಕೊಳ್ಳಿ' : 'Share Receipt to WhatsApp'}
            </a>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center justify-center gap-1.5 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-xs font-bold text-slate-700 hover:bg-slate-50"
            >
              {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
