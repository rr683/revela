import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";

const VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm"];
const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"];

interface FileUploadProps {
  onSubmit: (files: { video?: File; images?: File[] }, method: string) => void;
  disabled?: boolean;
}

export default function FileUpload({ onSubmit, disabled }: FileUploadProps) {
  const [video, setVideo] = useState<File | null>(null);
  const [images, setImages] = useState<File[]>([]);
  const [method, setMethod] = useState("splatfacto");

  const onDrop = useCallback((accepted: File[]) => {
    const vids: File[] = [];
    const imgs: File[] = [];

    for (const f of accepted) {
      const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
      if (VIDEO_EXTENSIONS.includes(ext)) {
        vids.push(f);
      } else if (IMAGE_EXTENSIONS.includes(ext)) {
        imgs.push(f);
      }
    }

    if (vids.length > 0) setVideo(vids[0]);
    if (imgs.length > 0) setImages((prev) => [...prev, ...imgs]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled,
  });

  const hasFiles = video || images.length > 0;

  const handleSubmit = () => {
    if (!hasFiles) return;
    onSubmit(
      {
        video: video || undefined,
        images: images.length > 0 ? images : undefined,
      },
      method,
    );
    setVideo(null);
    setImages([]);
  };

  const removeVideo = () => setVideo(null);
  const removeImage = (idx: number) =>
    setImages((prev) => prev.filter((_, i) => i !== idx));

  return (
    <div className="upload-section">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? "active" : ""} ${disabled ? "disabled" : ""}`}
      >
        <input {...getInputProps()} />
        <div className="dropzone-content">
          <span className="dropzone-icon">&#8682;</span>
          {isDragActive ? (
            <p>Drop files here...</p>
          ) : (
            <>
              <p>Drag & drop video or images here</p>
              <p className="hint">
                Video: MP4, MOV, AVI, MKV, WebM &middot; Images: JPG, PNG,
                TIFF, BMP
              </p>
            </>
          )}
        </div>
      </div>

      {hasFiles && (
        <div className="file-list">
          {video && (
            <div className="file-item">
              <span className="file-tag video">VIDEO</span>
              <span className="file-name">{video.name}</span>
              <span className="file-size">
                {(video.size / 1024 / 1024).toFixed(1)} MB
              </span>
              <button className="btn-remove" onClick={removeVideo}>
                &times;
              </button>
            </div>
          )}
          {images.map((img, i) => (
            <div className="file-item" key={`${img.name}-${i}`}>
              <span className="file-tag image">IMG</span>
              <span className="file-name">{img.name}</span>
              <span className="file-size">
                {(img.size / 1024).toFixed(0)} KB
              </span>
              <button className="btn-remove" onClick={() => removeImage(i)}>
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="upload-controls">
        <label>
          Method:
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            disabled={disabled}
          >
            <option value="splatfacto">Gaussian Splatting</option>
            <option value="nerfacto">NeRF</option>
          </select>
        </label>

        <button
          className="btn-primary"
          onClick={handleSubmit}
          disabled={!hasFiles || disabled}
        >
          {disabled ? "Uploading..." : "Start Reconstruction"}
        </button>
      </div>
    </div>
  );
}
