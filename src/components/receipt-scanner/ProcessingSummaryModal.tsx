import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { ProcessingStats } from "@/types/receipt";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

interface ProcessingSummaryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stats: ProcessingStats | null;
  receiptsCount: number;
}

export function ProcessingSummaryModal({
  open,
  onOpenChange,
  stats,
  receiptsCount
}: ProcessingSummaryModalProps) {
  if (!stats) return null;

  const missingFieldsCount = stats.receipts_extracted > 0 
    ? Math.round((stats.missing_receipts_estimate / stats.receipts_extracted) * 100)
    : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Processing Summary</DialogTitle>
          <DialogDescription>
            Detailed statistics from receipt extraction
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Overview */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-lg border bg-card">
              <div className="text-sm text-muted-foreground">Pages Processed</div>
              <div className="text-2xl font-semibold mt-1">{stats.pages_processed}</div>
            </div>
            <div className="p-4 rounded-lg border bg-card">
              <div className="text-sm text-muted-foreground">Receipts Detected</div>
              <div className="text-2xl font-semibold mt-1">{stats.receipts_detected}</div>
            </div>
            <div className="p-4 rounded-lg border bg-card">
              <div className="text-sm text-muted-foreground">Receipts Extracted</div>
              <div className="text-2xl font-semibold mt-1 text-green-600 dark:text-green-400">
                {stats.receipts_extracted}
              </div>
            </div>
            <div className="p-4 rounded-lg border bg-card">
              <div className="text-sm text-muted-foreground">Missing Estimate</div>
              <div className="text-2xl font-semibold mt-1 text-orange-600 dark:text-orange-400">
                {stats.missing_receipts_estimate}
              </div>
            </div>
          </div>

          {/* Detection Warning */}
          {stats.detection_warning && (
            <div className="p-4 rounded-lg border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
                <div>
                  <div className="font-semibold text-yellow-800 dark:text-yellow-200">
                    Detection Warning
                  </div>
                  <div className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                    Some receipts may not have been detected. Review the extracted receipts or edit missing values manually.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Per-page Stats */}
          {stats.page_stats && stats.page_stats.length > 0 && (
            <div>
              <h3 className="font-semibold mb-3">Per-Page Breakdown</h3>
              <div className="space-y-2">
                {stats.page_stats.map((pageStat, idx) => (
                  <div key={idx} className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">Page {pageStat.page_number}</span>
                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-muted-foreground">
                          {pageStat.detected} detected
                        </span>
                        <span className="text-green-600 dark:text-green-400">
                          {pageStat.successful} successful
                        </span>
                        {pageStat.rejected > 0 && (
                          <span className="text-red-600 dark:text-red-400">
                            {pageStat.rejected} rejected
                          </span>
                        )}
                      </div>
                    </div>
                    {pageStat.rejection_reasons.length > 0 && (
                      <div className="mt-2 text-xs text-muted-foreground">
                        <ul className="list-disc list-inside space-y-1">
                          {pageStat.rejection_reasons.slice(0, 3).map((reason, i) => (
                            <li key={i}>{reason}</li>
                          ))}
                          {pageStat.rejection_reasons.length > 3 && (
                            <li>...and {pageStat.rejection_reasons.length - 3} more</li>
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary Message */}
          <div className="p-4 rounded-lg border bg-muted/50">
            <div className="flex items-center gap-2">
              {stats.receipts_extracted > 0 ? (
                <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              )}
              <div>
                <div className="font-semibold">
                  {stats.receipts_extracted > 0 
                    ? `Successfully extracted ${stats.receipts_extracted} receipt${stats.receipts_extracted !== 1 ? 's' : ''}`
                    : 'No receipts were extracted'}
                </div>
                {stats.missing_receipts_estimate > 0 && (
                  <div className="text-sm text-muted-foreground mt-1">
                    Estimated {stats.missing_receipts_estimate} receipt{stats.missing_receipts_estimate !== 1 ? 's' : ''} may be missing
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

