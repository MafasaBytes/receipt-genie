import { motion } from "framer-motion";
import { Check, Loader2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import { ProcessingStatus } from "@/types/receipt";

interface Step {
  id: string;
  label: string;
  threshold: number;
}

const STEPS: Step[] = [
  { id: "upload", label: "Upload", threshold: 0 },
  { id: "processing", label: "Processing", threshold: 10 },
  { id: "results", label: "Results", threshold: 100 }
];

interface ProcessingStepsProps {
  status: ProcessingStatus;
}

export function ProcessingSteps({ status }: ProcessingStepsProps) {
  const getStepStatus = (step: Step, index: number) => {
    if (status.status === 'idle') return 'pending';
    if (status.status === 'error') return index === 0 ? 'completed' : 'error';
    if (status.status === 'completed') return 'completed';
    
    if (status.progress >= step.threshold) {
      const nextStep = STEPS[index + 1];
      if (!nextStep || status.progress < nextStep.threshold) {
        return 'active';
      }
      return 'completed';
    }
    return 'pending';
  };

  return (
    <div className="w-full py-6">
      <div className="flex items-center justify-between relative">
        {/* Progress line */}
        <div className="absolute top-5 left-8 right-8 h-0.5 bg-border">
          <motion.div 
            className="h-full bg-primary"
            initial={{ width: "0%" }}
            animate={{ 
              width: status.status === 'completed' 
                ? "100%" 
                : status.status === 'idle' 
                  ? "0%" 
                  : `${Math.min(status.progress, 100)}%`
            }}
            transition={{ duration: 0.3 }}
          />
        </div>

        {STEPS.map((step, index) => {
          const stepStatus = getStepStatus(step, index);
          
          return (
            <div key={step.id} className="flex flex-col items-center z-10">
              <motion.div
                initial={false}
                animate={{
                  scale: stepStatus === 'active' ? 1.1 : 1,
                }}
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center transition-colors duration-200",
                  stepStatus === 'completed' && "bg-primary",
                  stepStatus === 'active' && "bg-primary",
                  stepStatus === 'pending' && "bg-muted border-2 border-border",
                  stepStatus === 'error' && "bg-destructive"
                )}
              >
                {stepStatus === 'completed' && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    <Check className="w-5 h-5 text-primary-foreground" />
                  </motion.div>
                )}
                {stepStatus === 'active' && (
                  <Loader2 className="w-5 h-5 text-primary-foreground animate-spin" />
                )}
                {stepStatus === 'pending' && (
                  <Circle className="w-4 h-4 text-muted-foreground" />
                )}
                {stepStatus === 'error' && (
                  <span className="text-destructive-foreground font-medium">!</span>
                )}
              </motion.div>
              <span className={cn(
                "mt-2 text-xs font-medium transition-colors",
                stepStatus === 'active' && "text-primary",
                stepStatus === 'completed' && "text-foreground",
                stepStatus === 'pending' && "text-muted-foreground",
                stepStatus === 'error' && "text-destructive"
              )}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Status message */}
      <motion.p 
        key={status.message}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center text-sm text-muted-foreground mt-6"
      >
        {status.message}
      </motion.p>
    </div>
  );
}
