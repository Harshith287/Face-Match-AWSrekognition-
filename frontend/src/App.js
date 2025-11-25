
import React, { useState, useRef } from "react";
import Webcam from "react-webcam";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import env from "react-dotenv";

  const API_URL = process.env.REACT_APP_API_URL;
  const match_url = process.env.REACT_APP_MATCH_URL;

const App = () => {
  const webcamRef = useRef(null);
  const [capturedImage, setCapturedImage] = useState(null);
  const [status, setStatus] = useState("");
  const [matches, setMatches] = useState([]);
  const [err, setErr] = useState(null);
  const [startCamera, setStartCamera] = useState(false);
  const [picUpdated,setPicUpdated]=useState(false);
  const [selected, setSelected] = useState({});

  // Capture selfie
  const captureSelfie = () => {
    if (!startCamera) {
      setErr("Camera is not active.");
      return;
    }
    const imageSrc = webcamRef.current.getScreenshot();

    const img = new Image();
  img.src = imageSrc;

  img.onload = () => {
    const size = 300; // final circle size (adjust as needed)
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;

    const ctx = canvas.getContext("2d");
    
    // Draw circular mask
    ctx.beginPath();
    ctx.arc(size/2, size/2, size/2, 0, Math.PI * 2);
    ctx.closePath();
    ctx.clip();

    // Draw the image onto the circle
    ctx.drawImage(img, 0, 0, size, size);

    // Convert to base64
    const circularImage = canvas.toDataURL("image/jpeg");

    setCapturedImage(circularImage);
  };
    
    // setCapturedImage(imageSrc);
    setErr(null);
  };

  // Upload selfie to S3
  const handleUpload = async () => {
    if (!capturedImage) {
      setStatus("Please capture a selfie first.");
      return;
    }

    setStatus("Preparing upload...");
    setErr(null);
    setMatches([]);
    

    // Convert base64 → File object
    const res = await fetch(capturedImage);
    const blob = await res.blob();
    const file = new File([blob], "selfie.jpeg", { type: "image/jpeg" });

    // Step 1: Get presigned POST
    const resp = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        contentType: file.type,
      }),
    });

    if (!resp.ok) {
      setStatus("Error getting upload URL.");
      setMatches([]);
      return;
    }

    const { url, fields, key } = await resp.json();
    setStatus("Uploading selfie to S3...");

    // Step 2: Upload to S3
    const formData = new FormData();
    Object.entries(fields).forEach(([k, v]) => formData.append(k, v));
    formData.append("file", file);

    const uploadResp = await fetch(url, {
      method: "POST",
      body: formData,
    });

    if (uploadResp.ok) {
      setStatus("Selfie uploaded successfully!");
      setPicUpdated(!picUpdated);
    } else {
      setErr("Upload failed.");
      setStatus("");
      return;
    }
     // Step 3: Send match request
    const matchData = await fetch(match_url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, fields, key }),
    });

    const match_result = await matchData.json();
    setMatches(match_result.matches || []);
    console.log("Match result:", match_result);

    if (match_result.error)
    {
      setMatches([]);
       setErr(match_result.error);
    }

  };

  const handleClear=()=>{
    setCapturedImage(null);
    setStatus("");
    setMatches([]);
    setErr(null);
    setStartCamera(false);
    setPicUpdated(false);
  }

const downloadImage = async (url, filename,e) => {
  try {
    // e.stopPropagation();

    const res = await fetch(url, {
      method: "GET",
      cache: "no-cache",       // prevent 304 and force full CORS headers
      mode: "cors",
    });
    if (!res.ok) throw new Error(`Network response ${res.status}`);
    console.log('downloadBlobUrl response', res);
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    console.log('downloadBlobUrl blobUrl', blobUrl);

    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = blobUrl;
    a.download = filename;    
    a.target='_blank'          // suggested filename
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(blobUrl);
  } catch (err) {
    console.error('downloadBlobUrl error', err);
    // Optionally show user message or fallback to opening url
  }
};
const toggleSelect = (i) => {
  setSelected(prev => ({ ...prev, [i]: !prev[i] }));
};

const downloadAllSelected = async () => {
  const zip = new JSZip();
  const folder = zip.folder("matched_images");

  const selectedIndices = Object.keys(selected).filter(i => selected[i]);

  if (selectedIndices.length === 0) return;

  for (const i of selectedIndices) {
    const m = matches[i];
    const encodedPath = encodeURIComponent(m.image).replace(/%2F/g, "/");
    const url = m.imageUrl;

    const response = await fetch(url, { cache: "no-cache" });
    const blob = await response.blob();

    // Add to folder
    folder.file(`match_${i}.jpeg`, blob);
  }

  // Generate the zip & download
  zip.generateAsync({ type: "blob" }).then((zipFile) => {
    saveAs(zipFile, "selected_images.zip");
  });
};

return (
  <div className="container py-4">
    <div className="row justify-content-center">
      <div className="col-lg-6 col-md-8 col-sm-12 text-center d-flex flex-column align-items-center">

        <h2 className="mb-4 fw-bold">Fomo Pictures Matching</h2>

        {/* Start/Stop Camera */}
        <button 
          onClick={() => setStartCamera(!startCamera)}
          className="btn btn-primary mb-3 w-100"
        >
          {startCamera ? "Stop Camera" : "Start Camera"}
        </button>

        {/* Webcam */}
        {startCamera && (
          <div 
            className="rounded-circle mb-3 d-flex justify-content-center align-items-center shadow-sm bg-light"
            style={{
              width: "260px",
              height: "260px",
              overflow: "hidden",
              border: "3px solid #007bff"
            }}
          >
            <Webcam
              audio={false}
              ref={webcamRef}
              screenshotFormat="image/jpeg"
              videoConstraints={{ width: 300, height: 300, facingMode: "user" }}
              className="w-100 h-100"
              style={{ objectFit: "cover" }}
            />
          </div>
        )}

        {/* Capture Button */}
        <button 
          onClick={captureSelfie}
          className="btn btn-secondary mb-3 w-100"
        >
          Capture Selfie
        </button>

        {/* Selfie Preview */}
        {capturedImage && (
          <div className="text-center mb-4">
            <h5 className="fw-semibold">Selfie Preview</h5>
            <div
              className="rounded-circle mx-auto mt-2 shadow-sm"
              style={{
                width: "260px",
                height: "260px",
                overflow: "hidden",
              }}
            >
              <img 
                src={capturedImage}
                className="w-100 h-100"
                style={{ objectFit: "cover" }}
                alt="Selfie"
              />
            </div>
          </div>
        )}

        {/* Upload + Clear Buttons */}
        <div className="d-flex flex-column flex-sm-row gap-3 mb-3 w-100">
          <button 
            onClick={handleUpload} 
            className="btn btn-success w-100"
          >
            Upload Selfie
          </button>

          <button 
            onClick={handleClear} 
            className="btn btn-outline-danger w-100"
          >
            Clear
          </button>
        </div>

        {/* Status or Error */}
        {status && <p className="text-primary fw-semibold">{status}</p>}
        {err && <p className="text-danger fw-semibold">Error: {err}</p>}

        {/* No Matches */}
        {matches.length === 0 && picUpdated && !err && (
          <p className="mt-4 fw-medium">No matches found.</p>
        )}

        {/* Matches */}
        {matches.length > 0 && (
          <div className="mt-4 w-100">
            <h3 className="fw-bold mb-3 text-center">Matched Images</h3>

            {/* Download All Button */}
            {Object.values(selected).some(v => v) && (
              <div className="text-center mb-3">
                <button className="btn btn-success" onClick={downloadAllSelected}>
                  <i className="bi bi-download me-2"></i> Download All Selected
                </button>
              </div>
            )}

            {/* Cards */}
            <div className="row g-3 justify-content-center">
              {matches.map((m, i) => {
                const encodedPath = encodeURIComponent(m.image).replace(/%2F/g, "/");

                return (
                  <div key={i} className="col-lg-4 col-md-5 col-sm-6 col-12">
                    <div
                      onClick={() => toggleSelect(i)}
                      className={`card shadow-sm p-3 text-center ${
                        selected[i] ? "border border-primary" : ""
                      }`}
                      style={{ cursor: "pointer" }}
                    >
                      <input
                        type="checkbox"
                        className="form-check-input mb-2"
                        checked={!!selected[i]}
                        onChange={() => toggleSelect(i)}
                        onClick={e => e.stopPropagation()}
                      />

                      <img
                      src={m.imageUrl}
                      className="img-fluid rounded mb-2"
                      alt="Matched"
                      style={{
                        width: "100%",
                        height: "200px",
                        objectFit: "fill"
                      }}
                    />

                      <p className="mb-2">
                        <strong>Similarity:</strong> {m.similarity.toFixed(2)}%
                      </p>

                      <button
                        className="btn btn-primary w-100"
                        onClick={e => {
                          e.stopPropagation();
                          downloadImage(m.imageUrl, `match_${i}.jpeg`);
                        }}
                      >
                        Download
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </div>
    </div>
  </div>
);


};

export default App;
