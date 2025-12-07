export interface Receipt {
  id: string;
  store_name: string | null;
  date: string | null;
  total_amount: number | null;
  vat_amount: number | null;
  vat_percentage: number | null;
  currency: string | null;
  confidence_score?: number | null; // Accuracy/confidence score (0-1)
  modified?: boolean; // Frontend flag for edited receipts
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
