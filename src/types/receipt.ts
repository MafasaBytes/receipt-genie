export interface VATBreakdownEntry {
  vat_rate: number;
  tax_amount: number | null;
  base_amount: number | null;
}

export interface ReceiptItem {
  name: string | null;
  quantity: number | null;
  unit_price: number | null;
  line_total: number | null;
  vat_rate: number | null;
}

export interface Receipt {
  id: string;
  store_name: string | null;
  date: string | null;
  total_amount: number | null;
  vat_amount: number | null;
  vat_percentage: number | null;
  vat_percentage_effective: number | null;
  vat_breakdown: VATBreakdownEntry[] | null;
  items: ReceiptItem[] | null;
  description: string | null;
  currency: string | null;
  confidence_score?: number | null;
  modified?: boolean;
}

export interface ProcessingStats {
  pages_processed: number;
  receipts_detected: number;
  receipts_extracted: number;
  missing_receipts_estimate: number;
  detection_warning: boolean;
  page_stats: Array<{
    page_number: number;
    detected: number;
    successful: number;
    rejected: number;
    rejection_reasons: string[];
  }>;
}

export interface ProcessResult {
  receipts: Receipt[];
  stats: ProcessingStats | null;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  size: number;
}

export interface ProcessingStatus {
  status: 'idle' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  message: string;
}
