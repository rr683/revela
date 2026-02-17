import { Suspense, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Environment } from "@react-three/drei";
import * as THREE from "three";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";

interface ModelViewerProps {
  url: string;
  filename: string;
}

function PointCloudModel({ url }: { url: string }) {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);

  useEffect(() => {
    const loader = new PLYLoader();
    loader.load(
      url,
      (geo) => {
        geo.computeVertexNormals();
        // Center the geometry
        geo.computeBoundingBox();
        const center = new THREE.Vector3();
        geo.boundingBox!.getCenter(center);
        geo.translate(-center.x, -center.y, -center.z);
        setGeometry(geo);
      },
      undefined,
      (err) => console.error("PLY load error:", err),
    );
  }, [url]);

  if (!geometry) return null;

  const hasColors = geometry.hasAttribute("color");

  return (
    <points>
      <bufferGeometry attach="geometry" {...geometry} />
      <pointsMaterial
        attach="material"
        size={0.005}
        vertexColors={hasColors}
        color={hasColors ? undefined : "#6699ff"}
        sizeAttenuation
      />
    </points>
  );
}

function MeshModel({ url }: { url: string }) {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);

  useEffect(() => {
    const loader = new PLYLoader();
    loader.load(
      url,
      (geo) => {
        geo.computeVertexNormals();
        geo.computeBoundingBox();
        const center = new THREE.Vector3();
        geo.boundingBox!.getCenter(center);
        geo.translate(-center.x, -center.y, -center.z);
        setGeometry(geo);
      },
      undefined,
      (err) => console.error("Mesh load error:", err),
    );
  }, [url]);

  if (!geometry) return null;

  const hasColors = geometry.hasAttribute("color");

  return (
    <mesh>
      <bufferGeometry attach="geometry" {...geometry} />
      <meshStandardMaterial
        attach="material"
        vertexColors={hasColors}
        color={hasColors ? undefined : "#cccccc"}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

export default function ModelViewer({ url, filename }: ModelViewerProps) {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  const isMesh = ext === ".obj" || ext === ".stl" || filename.includes("mesh");

  return (
    <div className="viewer-container">
      <Canvas camera={{ position: [0, 0, 2], fov: 60 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 5, 5]} intensity={1} />
        <Suspense fallback={null}>
          {isMesh ? <MeshModel url={url} /> : <PointCloudModel url={url} />}
          <Environment preset="studio" />
        </Suspense>
        <OrbitControls
          enableDamping
          dampingFactor={0.1}
          rotateSpeed={0.5}
          zoomSpeed={0.8}
        />
      </Canvas>
      <div className="viewer-controls-hint">
        Drag to rotate &middot; Scroll to zoom &middot; Right-drag to pan
      </div>
    </div>
  );
}
