import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Scan, RotateCcw, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FileUploader } from "./FileUploader";
import { ProcessingSteps } from "./ProcessingSteps";
import { ReceiptsTable } from "./ReceiptsTable";
import { EditableReceiptTable } from "./EditableReceiptTable";
import { ExportButtons } from "./ExportButtons";
import { ProcessingSummaryModal } from "./ProcessingSummaryModal";
import { Receipt, ProcessingStatus, UploadResponse, ProcessResult } from "@/types/receipt";
import { uploadPdf, processPdf } from "@/services/api";
import { toast } from "@/hooks/use-toast";

export function ReceiptScanner() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadResponse, setUploadResponse] = useState<UploadResponse | null>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [processingStats, setProcessingStats] = useState<any>(null);
  const [showSummaryModal, setShowSummaryModal] = useState(false);
  const [status, setStatus] = useState<ProcessingStatus>({
    status: 'idle',
    progress: 0,
    message: 'Select a PDF file to begin'
  });

  const handleFileSelect = useCallback((selectedFile: File) => {
    setFile(selectedFile);
    setStatus({
      status: 'idle',
      progress: 0,
      message: `Ready to process: ${selectedFile.name}`
    });
    setReceipts([]);
    setUploadResponse(null);
  }, []);

  const handleClear = useCallback(() => {
    setFile(null);
    setUploadResponse(null);
    setReceipts([]);
    setStatus({
      status: 'idle',
      progress: 0,
      message: 'Select a PDF file to begin'
    });
  }, []);

  const handleProcess = useCallback(async () => {
    if (!file) return;

    try {
      // Upload phase
      setStatus({
        status: 'uploading',
        progress: 5,
        message: 'Uploading PDF...'
      });

      const uploadResult = await uploadPdf(file);
      setUploadResponse(uploadResult);

      // Processing phase
      setStatus({
        status: 'processing',
        progress: 10,
        message: 'Processing receipts...'
      });

      const result: ProcessResult = await processPdf(
        uploadResult.file_id,
        (progress) => {
          setStatus(prev => ({
            ...prev,
            progress,
            message: progress < 30 
              ? 'Converting PDF to images...'
              : progress < 50 
                ? 'Detecting receipts on pages...'
                : progress < 70 
                  ? 'Running OCR on detected receipts...'
                : progress < 90 
                  ? 'Extracting fields with AI...'
                  : 'Finalizing and normalizing data...'
          }));
        }
      );

      setReceipts(result.receipts);
      setProcessingStats(result.stats);
      setStatus({
        status: 'completed',
        progress: 100,
        message: `Successfully extracted ${result.receipts.length} receipt${result.receipts.length !== 1 ? 's' : ''}`
      });

      // Show summary modal if stats available
      if (result.stats) {
        setShowSummaryModal(true);
      }

      toast({
        title: "Processing complete",
        description: `Found ${result.receipts.length} receipt${result.receipts.length !== 1 ? 's' : ''} in your document.`
      });

    } catch (error) {
      setStatus({
        status: 'error',
        progress: 0,
        message: 'An error occurred during processing'
      });
      toast({
        title: "Processing failed",
        description: "Please try again or check your PDF file.",
        variant: "destructive"
      });
    }
  }, [file]);

  const isProcessing = status.status === 'uploading' || status.status === 'processing';

  return (
    <div className="w-full max-w-4xl mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-6">
          <Scan className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-3xl font-semibold text-foreground tracking-tight">
          Receipt Scanner
        </h1>
        <p className="text-muted-foreground mt-2 max-w-md mx-auto">
          Upload a PDF with receipts and extract structured data automatically
        </p>
      </motion.div>

      {/* Main Card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-card rounded-2xl border border-border p-8 shadow-card"
      >
        {/* File Uploader */}
        <FileUploader
          onFileSelect={handleFileSelect}
          selectedFile={file}
          onClear={handleClear}
          disabled={isProcessing}
        />

        {/* Processing Steps */}
        {file && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-8"
          >
            <ProcessingSteps status={status} />
          </motion.div>
        )}

        {/* Action Buttons */}
        {file && status.status !== 'completed' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-center gap-4 mt-6"
          >
            <Button
              onClick={handleProcess}
              disabled={isProcessing}
              size="lg"
              className="gap-2 min-w-40"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Scan className="w-4 h-4" />
                  Process Receipts
                </>
              )}
            </Button>
          </motion.div>
        )}
      </motion.div>

      {/* Results Section */}
      <AnimatePresence>
        {receipts.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -24 }}
            transition={{ delay: 0.1 }}
            className="mt-8 space-y-6"
          >
            {/* Results Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  Extracted Receipts
                </h2>
                <p className="text-sm text-muted-foreground">
                  {receipts.length} receipt{receipts.length !== 1 ? 's' : ''} found
                </p>
              </div>
              <div className="flex items-center gap-3">
                <ExportButtons fileId={uploadResponse?.file_id || null} disabled={isProcessing} />
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleClear}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <RotateCcw className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Detection Warning Banner */}
            {processingStats && processingStats.detection_warning && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 rounded-lg border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20"
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-semibold text-yellow-800 dark:text-yellow-200">
                      Detection Warning
                    </div>
                    <div className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                      Some receipts may not have been detected. Review the detected receipts or edit missing values manually.
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Results Table - Editable */}
            <EditableReceiptTable 
              receipts={receipts}
              onReceiptUpdate={(receiptId, updates) => {
                setReceipts(prev => prev.map(r => 
                  r.id === receiptId ? { ...r, ...updates, modified: true } : r
                ));
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Processing Summary Modal */}
      {processingStats && (
        <ProcessingSummaryModal
          open={showSummaryModal}
          onOpenChange={setShowSummaryModal}
          stats={processingStats}
          receiptsCount={receipts.length}
        />
      )}
    </div>
  );
}
