export interface Receipt {
  id: string;
  store_name: string | null;
  date: string | null;
  total_amount: number | null;
  vat_amount: number | null;
  vat_percentage: number | null;
  currency: string | null;
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
