export interface Job {
  id: string;
  status: JobStatus;
  method: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  input_video: string | null;
  input_image_dir: string | null;
  num_frames: number | null;
  duration_seconds: number | null;
  quality: QualityMetrics | null;
  outputs: JobOutputs | null;
}

export type JobStatus =
  | "pending"
  | "preprocessing"
  | "pose_estimation"
  | "training"
  | "exporting"
  | "completed"
  | "failed"
  | "cancelled";

export interface QualityMetrics {
  psnr?: number;
  ssim?: number;
  lpips?: number;
}

export interface JobOutputs {
  output_files: Record<string, string>;
}

export interface OutputFile {
  name: string;
  path: string;
  size_bytes: number;
  suffix: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
}
