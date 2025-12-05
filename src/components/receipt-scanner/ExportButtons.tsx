import { motion } from "framer-motion";
import { FileSpreadsheet, FileDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Receipt } from "@/types/receipt";
import { downloadCsv, downloadExcel } from "@/services/api";
import { useState } from "react";
import { toast } from "@/hooks/use-toast";

interface ExportButtonsProps {
  receipts: Receipt[];
  disabled?: boolean;
}

export function ExportButtons({ receipts, disabled }: ExportButtonsProps) {
  const [exporting, setExporting] = useState<'csv' | 'excel' | null>(null);

  const handleExportCsv = async () => {
    setExporting('csv');
    try {
      await downloadCsv(receipts);
      toast({
        title: "Export successful",
        description: "Your CSV file has been downloaded."
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description: "Failed to export CSV file.",
        variant: "destructive"
      });
    } finally {
      setExporting(null);
    }
  };

  const handleExportExcel = async () => {
    setExporting('excel');
    try {
      await downloadExcel(receipts);
      toast({
        title: "Export successful",
        description: "Your Excel file has been downloaded."
      });
    } catch (error) {
      toast({
        title: "Export failed",
        description: "Failed to export Excel file.",
        variant: "destructive"
      });
    } finally {
      setExporting(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.2 }}
      className="flex gap-3"
    >
      <Button
        variant="outline"
        onClick={handleExportCsv}
        disabled={disabled || exporting !== null}
        className="gap-2"
      >
        {exporting === 'csv' ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <FileDown className="w-4 h-4" />
        )}
        Download CSV
      </Button>
      <Button
        variant="outline"
        onClick={handleExportExcel}
        disabled={disabled || exporting !== null}
        className="gap-2"
      >
        {exporting === 'excel' ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <FileSpreadsheet className="w-4 h-4" />
        )}
        Download Excel
      </Button>
    </motion.div>
  );
}
