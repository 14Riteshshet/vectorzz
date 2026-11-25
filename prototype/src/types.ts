export type Language = 'kn' | 'en';
export type TextZoom = 'normal' | 'large';
export type CultivatorStatus = 'landowner' | 'tenant';
export type StressScenario = 'normal' | 'drought' | 'waterlogged';

export interface PlotRecord {
  id: string;
  surveyNo: string;
  ulpin: string;
  taluk: string;
  hobli: string;
  village: string;
  district: string;
  crop: string;
  cropKn: string;
  areaAcres: number;
  farmerName: string;
  farmerNameKn: string;
  gpsLat: number;
  gpsLon: number;
  sumInsuredInr: number;
  farmerPremiumInr: number;
  govtSubsidyInr: number;
  insurerName: string;
  insurerShort: string;
  blockOfficer: string;
  blockOfficerPhone: string;
  notifiedSeason: string;
  aadhaarBankLinked: boolean;
}

export interface ScenarioTelemetry {
  id: StressScenario;
  labelEn: string;
  labelKn: string;
  ndmi: number;
  soilMoisturePct: number;
  et0MmDay: number;
  actionEn: string;
  actionKn: string;
  kannadaTranscript: string;
  diagnosisTitleEn: string;
  diagnosisTitleKn: string;
  diagnosisDetailEn: string;
  diagnosisDetailKn: string;
  thresholdCrossed: boolean;
  payoutInr: number;
}

export interface CapturedPhotoProof {
  sha256: string;
  lat: number;
  lon: number;
  timestampIso: string;
  diagnosisTitleEn: string;
  diagnosisTitleKn: string;
  diagnosisDetailEn: string;
  diagnosisDetailKn: string;
  synced: boolean;
}
