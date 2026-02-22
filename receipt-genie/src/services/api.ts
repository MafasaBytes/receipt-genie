import { Receipt, UploadResponse, ProcessResult } from "@/types/receipt";

// Backend API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Upload a PDF or image file
 * POST /api/upload/pdf or /api/upload/file
 */
export async function uploadPdf(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  
  // Use /file endpoint which supports both PDF and images
  const response = await fetch(`${API_BASE_URL}/api/upload/file`, {
    method: 'POST',
    body: formData
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || `Upload failed: ${response.statusText}`);
  }
  
  const data = await response.json();
  return {
    file_id: data.file_id,
    filename: data.filename,
    size: data.file_size
  };
}

/**
 * Process uploaded PDF with progress polling
 * POST /api/process/pdf -> GET /api/process/status/{job_id} -> GET /api/process/receipts/{file_id}
 */
export async function processPdf(
  fileId: string, 
  onProgress?: (progress: number) => void
): Promise<ProcessResult> {
  // Start processing job
  const processResponse = await fetch(
    `${API_BASE_URL}/api/process/pdf?file_id=${encodeURIComponent(fileId)}`,
    { method: 'POST' }
  );
  
  if (!processResponse.ok) {
    const error = await processResponse.json().catch(() => ({ detail: 'Processing failed' }));
    throw new Error(error.detail || `Processing failed: ${processResponse.statusText}`);
  }
  
  const processData = await processResponse.json();
  const jobId = processData.job_id;
  
  // Poll job status until complete
  const pollInterval = 2000; // 2 seconds (reduced polling frequency)
  const maxWaitTime = 1200000; // 20 minutes (increased for processing many receipts with international support and complex VAT calculations)
  const startTime = Date.now();
  
  while (Date.now() - startTime < maxWaitTime) {
    const statusResponse = await fetch(`${API_BASE_URL}/api/process/status/${jobId}`);
    
    if (!statusResponse.ok) {
      throw new Error(`Failed to get job status: ${statusResponse.statusText}`);
    }
    
    const statusData = await statusResponse.json();
    const status = statusData.status;
    const progress = statusData.progress || 0;
    
    // Update progress callback
    onProgress?.(progress);
    
    if (status === 'completed') {
      // Fetch receipts
      const receiptsResponse = await fetch(`${API_BASE_URL}/api/process/receipts/${fileId}`);
      
      if (!receiptsResponse.ok) {
        throw new Error(`Failed to fetch receipts: ${receiptsResponse.statusText}`);
      }
      
      const receiptsData = await receiptsResponse.json();
      // Handle enhanced response with stats
      if (receiptsData.receipts) {
        return {
          receipts: mapBackendReceiptsToFrontend(receiptsData.receipts || []),
          stats: {
            pages_processed: receiptsData.pages_processed || 0,
            receipts_detected: receiptsData.receipts_detected || 0,
            receipts_extracted: receiptsData.receipts_extracted || 0,
            missing_receipts_estimate: receiptsData.missing_receipts_estimate || 0,
            detection_warning: receiptsData.detection_warning || false,
            page_stats: receiptsData.page_stats || []
          }
        };
      }
      // Legacy format
      return {
        receipts: mapBackendReceiptsToFrontend(receiptsData || []),
        stats: null
      };
    }
    
    if (status === 'failed') {
      throw new Error(statusData.error_message || 'Processing failed');
    }
    
    // Wait before next poll
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  throw new Error('Processing timeout - job took too long');
}

/**
 * Update a receipt
 * PATCH /api/process/receipt/{receipt_id}
 */
export async function updateReceipt(
  receiptId: number,
  updates: Partial<Receipt>
): Promise<Receipt> {
  const response = await fetch(`${API_BASE_URL}/api/process/receipt/${receiptId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates)
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Update failed' }));
    throw new Error(error.detail || `Update failed: ${response.statusText}`);
  }
  
  const data = await response.json();
  return mapBackendReceiptsToFrontend([data])[0];
}

/**
 * Get file statistics
 * GET /api/process/file/{file_id}/stats
 */
export async function getFileStats(fileId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/process/file/${encodeURIComponent(fileId)}/stats`);
  
  if (!response.ok) {
    throw new Error(`Failed to get stats: ${response.statusText}`);
  }
  
  return await response.json();
}

/**
 * Map backend receipt format to frontend format
 */
function mapBackendReceiptsToFrontend(backendReceipts: any[]): Receipt[] {
  return backendReceipts.map((receipt) => {
    // Calculate VAT percentage if we have tax_amount and total_amount
    // Try both methods: tax-inclusive (EU style) and tax-exclusive (US style)
    let vatPercentage: number | null = null;
    if (receipt.tax_amount && receipt.total_amount && receipt.total_amount > 0) {
      const tax = receipt.tax_amount;
      const total = receipt.total_amount;
      
      // Method 1: Total INCLUDES tax (common in EU, UK, etc.)
      // VAT% = (tax / (total - tax)) * 100
      const subtotalInclusive = total - tax;
      if (subtotalInclusive > 0) {
        const vatPctInclusive = (tax / subtotalInclusive) * 100;
        // EU rates typically 5-27%, US rates 0-10%
        if (5.0 <= vatPctInclusive && vatPctInclusive <= 30.0) {
          vatPercentage = vatPctInclusive;
        }
      }
      
      // Method 2: Total EXCLUDES tax (common in US, Canada)
      // VAT% = (tax / total) * 100
      if (vatPercentage === null && total > 0) {
        const vatPctExclusive = (tax / total) * 100;
        if (0.0 <= vatPctExclusive && vatPctExclusive <= 15.0) {
          vatPercentage = vatPctExclusive;
        }
      }
      
      // Fallback: use inclusive method if both seem reasonable
      if (vatPercentage === null && subtotalInclusive > 0) {
        vatPercentage = (tax / subtotalInclusive) * 100;
      }
    }
    
    // If backend already provided vat_percentage or vat_percentage_effective, use it (most accurate)
    if (receipt.vat_percentage_effective !== null && receipt.vat_percentage_effective !== undefined) {
      vatPercentage = receipt.vat_percentage_effective;
    } else if (receipt.vat_percentage !== null && receipt.vat_percentage !== undefined) {
      vatPercentage = receipt.vat_percentage;
    }
    
    return {
      id: receipt.id?.toString() || receipt.receipt_number?.toString() || '',
      store_name: receipt.merchant_name || null,
      date: receipt.date || null,
      total_amount: receipt.total_amount || null,
      vat_amount: receipt.tax_amount || null,
      vat_percentage: vatPercentage,
      vat_percentage_effective: receipt.vat_percentage_effective || null,
      vat_breakdown: receipt.vat_breakdown || null,
      items: receipt.items || null,
      currency: receipt.currency || "EUR", // Default to EUR if not detected (safety fallback)
      confidence_score: receipt.confidence_score || null
    };
  });
}

/**
 * Download receipts as CSV
 * GET /api/export/csv?file_id={file_id}
 */
export async function downloadCsv(fileId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/export/csv?file_id=${encodeURIComponent(fileId)}`);
  
  if (!response.ok) {
    throw new Error(`Failed to download CSV: ${response.statusText}`);
  }
  
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `receipts_${new Date().toISOString().split('T')[0]}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Download receipts as Excel
 * GET /api/export/excel?file_id={file_id}
 */
export async function downloadExcel(fileId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/export/excel?file_id=${encodeURIComponent(fileId)}`);
  
  if (!response.ok) {
    throw new Error(`Failed to download Excel: ${response.statusText}`);
  }
  
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `receipts_${new Date().toISOString().split('T')[0]}.xlsx`;
  link.click();
  URL.revokeObjectURL(url);
}

// LLM Extraction Prompt Template (placeholder)
export const LLM_EXTRACTION_PROMPT = `
You are an information extraction model.

Extract the following fields from the OCR text of a receipt:
- store_name
- date
- total_amount
- vat_amount
- vat_percentage
- currency

Return valid JSON only, strictly with these fields.
If values are missing, use null.
The OCR text is below:

{{OCR_TEXT}}
`;
