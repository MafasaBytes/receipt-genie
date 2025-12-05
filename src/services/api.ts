import { Receipt, UploadResponse } from "@/types/receipt";

// Mock data for development
const MOCK_RECEIPTS: Receipt[] = [
  {
    id: "1",
    store_name: "Sample Store",
    date: "2024-10-22",
    total_amount: 45.90,
    vat_amount: 5.50,
    vat_percentage: 12.0,
    currency: "EUR"
  },
  {
    id: "2",
    store_name: "Coffee Spot",
    date: "2024-10-21",
    total_amount: 3.90,
    vat_amount: 0.32,
    vat_percentage: 8.0,
    currency: "EUR"
  },
  {
    id: "3",
    store_name: "Tech Electronics",
    date: "2024-10-20",
    total_amount: 299.99,
    vat_amount: 47.89,
    vat_percentage: 19.0,
    currency: "EUR"
  },
  {
    id: "4",
    store_name: "Grocery Mart",
    date: "2024-10-19",
    total_amount: 67.45,
    vat_amount: 4.50,
    vat_percentage: 7.0,
    currency: "EUR"
  }
];

// Simulated delay for realistic UX
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Upload a PDF file
 * POST /upload_pdf
 */
export async function uploadPdf(file: File): Promise<UploadResponse> {
  await delay(1000); // Simulate upload time
  
  // In production, this would upload to the backend
  // const formData = new FormData();
  // formData.append('file', file);
  // const response = await fetch('/api/upload_pdf', { method: 'POST', body: formData });
  
  return {
    file_id: `file_${Date.now()}`,
    filename: file.name,
    size: file.size
  };
}

/**
 * Process uploaded PDF
 * POST /process_pdf
 */
export async function processPdf(
  fileId: string, 
  onProgress?: (progress: number) => void
): Promise<Receipt[]> {
  // Simulate processing steps
  const steps = [
    { progress: 10, delay: 500 },
    { progress: 30, delay: 800 },
    { progress: 50, delay: 600 },
    { progress: 70, delay: 700 },
    { progress: 90, delay: 500 },
    { progress: 100, delay: 300 }
  ];

  for (const step of steps) {
    await delay(step.delay);
    onProgress?.(step.progress);
  }

  // In production:
  // const response = await fetch('/api/process_pdf', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ file_id: fileId })
  // });
  // return response.json();

  return MOCK_RECEIPTS;
}

/**
 * Download receipts as CSV
 * GET /download_csv
 */
export async function downloadCsv(receipts: Receipt[]): Promise<void> {
  const headers = ['Store Name', 'Date', 'Total Amount', 'VAT Amount', 'VAT %', 'Currency'];
  const rows = receipts.map(r => [
    r.store_name || '',
    r.date || '',
    r.total_amount?.toFixed(2) || '',
    r.vat_amount?.toFixed(2) || '',
    r.vat_percentage?.toFixed(1) || '',
    r.currency || ''
  ]);
  
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');
  
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `receipts_${new Date().toISOString().split('T')[0]}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Download receipts as Excel
 * GET /download_excel
 */
export async function downloadExcel(receipts: Receipt[]): Promise<void> {
  // For now, download as CSV with .xlsx extension
  // In production, use a library like xlsx or call backend endpoint
  const headers = ['Store Name', 'Date', 'Total Amount', 'VAT Amount', 'VAT %', 'Currency'];
  const rows = receipts.map(r => [
    r.store_name || '',
    r.date || '',
    r.total_amount?.toFixed(2) || '',
    r.vat_amount?.toFixed(2) || '',
    r.vat_percentage?.toFixed(1) || '',
    r.currency || ''
  ]);
  
  // Tab-separated for basic Excel compatibility
  const content = [
    headers.join('\t'),
    ...rows.map(row => row.join('\t'))
  ].join('\n');
  
  const blob = new Blob([content], { type: 'application/vnd.ms-excel;charset=utf-8;' });
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
