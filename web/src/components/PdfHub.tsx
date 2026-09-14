import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import ReactMarkdown from "react-markdown";
import { apiClient, ApiError } from "../api/client";
import type { StudyDocumentDetail } from "../api/client";
import "../styles/pdf-hub.css";

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Too many requests. Please try again later.";
    return error.message;
  }
  return fallback;
}

function MarkdownText({ value }: { value: string }) {
  return (
    <div className="pdf-hub__markdown">
      <ReactMarkdown
        urlTransform={(url) => /^https?:\/\//i.test(url) ? url : ""}
        components={{
          a: ({ href, children }) => href ? (
            <a href={href} target="_blank" rel="noreferrer">{children}</a>
          ) : <span>{children}</span>,
        }}
      >
        {value}
      </ReactMarkdown>
    </div>
  );
}

export function PdfHub() {
  const [document, setDocument] = useState<StudyDocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"upload" | "analyze" | "refresh" | "lesson" | "assess" | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null);
  const [lesson, setLesson] = useState<
    Awaited<ReturnType<typeof apiClient.generateConceptLesson>>["lesson"] | null
  >(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<
    Awaited<ReturnType<typeof apiClient.assessConceptAnswer>> | null
  >(null);
  const requestVersion = useRef(0);
  const operationActive = useRef(false);

  useEffect(() => {
    const id = localStorage.getItem("feddy_document_id");
    const version = ++requestVersion.current;
    if (id) {
      void apiClient.getDocument(id).then((saved) => {
        if (version === requestVersion.current) setDocument(saved);
      }).catch((failure: unknown) => {
        if (version !== requestVersion.current) return;
        if (failure instanceof ApiError && failure.status === 404) {
          localStorage.removeItem("feddy_document_id");
        }
        setError(errorMessage(failure, "Could not restore your document."));
      });
    }
    return () => { requestVersion.current += 1; };
  }, []);

  async function chooseFile(file: File | undefined) {
    if (!file || operationActive.current) return;
    if (!/\.(pdf|txt)$/i.test(file.name)) {
      setError("Please choose a PDF or TXT file.");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setError("Files must be 25 MB or smaller.");
      return;
    }
    operationActive.current = true;
    const version = ++requestVersion.current;
    setBusy("upload");
    setError(null);
    setDocument(null);
    localStorage.removeItem("feddy_document_id");
    try {
      const uploaded = await apiClient.uploadDocument(file);
      if (version !== requestVersion.current) return;
      localStorage.setItem("feddy_document_id", uploaded.documentId);
      const saved = await apiClient.getDocument(uploaded.documentId);
      if (version === requestVersion.current) setDocument(saved);
    } catch (failure) {
      if (version === requestVersion.current) {
        setError(errorMessage(failure, "Could not load the uploaded document."));
      }
    } finally {
      operationActive.current = false;
      if (version === requestVersion.current) setBusy(null);
    }
  }

  async function refreshDocument() {
    const id = document?.documentId || localStorage.getItem("feddy_document_id");
    if (!id || operationActive.current) return;
    operationActive.current = true;
    const version = ++requestVersion.current;
    setBusy("refresh");
    setError(null);
    try {
      const saved = await apiClient.getDocument(id);
      if (version === requestVersion.current) setDocument(saved);
    } catch (failure) {
      if (version === requestVersion.current) {
        setError(errorMessage(failure, "Could not refresh the document."));
      }
    } finally {
      operationActive.current = false;
      if (version === requestVersion.current) setBusy(null);
    }
  }

  async function analyzeDocument() {
    if (!document || operationActive.current) return;
    operationActive.current = true;
    const id = document.documentId;
    const version = ++requestVersion.current;
    setBusy("analyze");
    setError(null);
    try {
      const result = await apiClient.analyzeDocument(id);
      if (version !== requestVersion.current) return;
      setDocument((current) => {
        if (!current || current.documentId !== id) return current;
        return {
          ...current,
          analysisStatus: result.analysisStatus,
          analysis: result.analysisStatus === "ready" ? result.analysis : null,
          analysisError: "",
        };
      });
    } catch (failure) {
      if (version === requestVersion.current) {
        const message = errorMessage(failure, "Analysis could not be completed.");
        setDocument((current) => {
          if (!current || current.documentId !== id) return current;
          return {
            ...current,
            analysisStatus: "failed",
            analysis: null,
            analysisError: message,
          };
        });
        setError(message);
      }
    } finally {
      operationActive.current = false;
      if (version === requestVersion.current) setBusy(null);
    }
  }

  useEffect(() => {
    setSelectedConceptId(null);
    setLesson(null);
  }, [document?.documentId, document?.analysis]);

  useEffect(() => {
    setAnswer("");
    setFeedback(null);
  }, [document?.documentId, selectedConceptId, lesson]);

  async function submitAnswer() {
    if (!document || !selectedConceptId || !answer.trim() || operationActive.current) return;
    operationActive.current = true;
    const version = ++requestVersion.current;
    const conceptId = selectedConceptId;
    setBusy("assess");
    setFeedback(null);
    setError(null);
    try {
      const result = await apiClient.assessConceptAnswer(
        document.documentId, conceptId, answer.trim()
      );
      if (version !== requestVersion.current) return;
      if (result.topicId !== conceptId) {
        throw new Error("Feedback did not match the selected concept.");
      }
      setFeedback(result);
    } catch (failure) {
      if (version === requestVersion.current) {
        setError(errorMessage(failure, "Could not review your explanation."));
      }
    } finally {
      operationActive.current = false;
      if (version === requestVersion.current) setBusy(null);
    }
  }

  async function teachConcept(conceptId: string) {
    if (!document || operationActive.current) return;
    operationActive.current = true;
    const version = ++requestVersion.current;
    setSelectedConceptId(conceptId);
    setLesson(null);
    setError(null);
    setBusy("lesson");
    try {
      const result = await apiClient.generateConceptLesson(
        document.documentId, conceptId
      );
      if (version !== requestVersion.current) return;
      if (result.topicId !== conceptId) {
        throw new Error("Lesson did not match the selected concept.");
      }
      setLesson(result.lesson);
    } catch (failure) {
      if (version === requestVersion.current) {
        setError(errorMessage(failure, "Could not generate this lesson."));
      }
    } finally {
      operationActive.current = false;
      if (version === requestVersion.current) setBusy(null);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    void chooseFile(file);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    void chooseFile(event.dataTransfer.files[0]);
  }

  function clearDocument() {
    if (operationActive.current) return;
    requestVersion.current += 1;
    localStorage.removeItem("feddy_document_id");
    setDocument(null);
    setError(null);
  }

  return (
    <section className="pdf-hub" aria-labelledby="pdf-hub-title">
      <div className="pdf-hub__heading">
        <div>
          <p className="pdf-hub__eyebrow">Study materials</p>
          <h2 id="pdf-hub-title">Understand your notes</h2>
        </div>
      </div>
      <p className="pdf-hub__description">
        Upload your material, then analyze its concepts with Feddy.
      </p>

      <label
        className={`pdf-hub__dropzone${isDragging ? " pdf-hub__dropzone--active" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          className="pdf-hub__input"
          type="file"
          accept=".pdf,.txt"
          disabled={busy !== null}
          onChange={handleFileChange}
        />
        <strong>{busy === "upload" ? "Uploading..." : "Drop a PDF or TXT file here"}</strong>
        <span>or choose from your device</span>
        <small>Up to 25 MB. Extraction processes up to 80 PDF pages and 240,000 characters.</small>
      </label>

      {error && <p className="pdf-hub__error" role="alert">{error}</p>}
      {!document && localStorage.getItem("feddy_document_id") && (
        <button type="button" disabled={busy !== null} onClick={() => void refreshDocument()}>
          Reload saved document
        </button>
      )}

      {document && (
        <section className="pdf-hub__results" aria-live="polite">
          <h3>{document.filename}</h3>
          <p>
            Extraction: {document.extractionStatus}.
            {" "}Processed {document.pagesProcessed} of {document.totalPages} pages.
          </p>
          {document.extractionStatus === "partial" && (
            <p>Coverage is partial. Analysis can only use the extracted material.</p>
          )}
          {document.extractionStatus === "failed" ? (
            <p>No readable source text is available. Try a PDF with selectable text or a TXT file.</p>
          ) : (
            <>
              <p>Analysis: {busy === "analyze" ? "processing" : document.analysisStatus}</p>
              {!document.analysis && (
                <>
                  <p>Analysis uses all extracted text. Larger documents may take longer to process.</p>
                  <button type="button" disabled={busy !== null} onClick={() => void analyzeDocument()}>
                    {busy === "analyze" ? "Analyzing..." :
                      document.analysisStatus === "processing" ? "Check or resume analysis" :
                      document.analysisStatus === "failed" ? "Retry analysis" : "Analyze document"}
                  </button>
                </>
              )}
              {document.analysisError && <p>{document.analysisError}</p>}
              {document.analysis && (
                <>
                  <p>{document.analysis.overview}</p>
                  <h3>Concepts from your material</h3>
                  {document.analysis.concepts.length === 0 && (
                    <p>No supported learning concepts were identified in this material.</p>
                  )}
                  {document.analysis.concepts.map((concept) => (
                    <article key={concept.id} className="pdf-hub__lesson">
                      <h4>{concept.title}</h4>
                      <p>{concept.description}</p>
                      <small>Supporting pages: {concept.pages.join(", ")}</small>
                      <div>
                        <button
                          type="button"
                          disabled={busy !== null}
                          onClick={() => void teachConcept(concept.id)}
                        >
                          {busy === "lesson" && selectedConceptId === concept.id
                            ? "Preparing lesson..." : "Teach this concept"}
                        </button>
                      </div>
                      {selectedConceptId === concept.id && lesson && (
                        <section
                          className="pdf-hub__lesson-reading"
                          aria-labelledby={`lesson-title-${concept.id}`}
                        >
                          <header className="pdf-hub__lesson-header">
                            <div>
                              <p className="pdf-hub__lesson-label">Selected concept</p>
                              <h4 id={`lesson-title-${concept.id}`}>{concept.title}</h4>
                            </div>
                            <small>Supporting pages: {concept.pages.join(", ")}</small>
                          </header>
                          <section aria-labelledby={`lesson-explanation-${concept.id}`}>
                            <h5 id={`lesson-explanation-${concept.id}`}>Explanation</h5>
                            <MarkdownText value={lesson.explanation} />
                          </section>
                          <section aria-labelledby={`lesson-example-${concept.id}`}>
                            <h5 id={`lesson-example-${concept.id}`}>Example</h5>
                            <MarkdownText value={lesson.example} />
                          </section>
                          <section aria-labelledby={`lesson-ideas-${concept.id}`}>
                            <h5 id={`lesson-ideas-${concept.id}`}>Key ideas</h5>
                            <ul>{lesson.key_ideas.map((idea, index) => (
                              <li key={index}><MarkdownText value={idea} /></li>
                            ))}</ul>
                          </section>
                          <details className="pdf-hub__questions">
                            <summary>Check your understanding</summary>
                            <ul>{lesson.questions.map((question, index) => (
                              <li key={index}><MarkdownText value={question} /></li>
                            ))}</ul>
                          </details>
                          <small>Lesson sources: {lesson.sources.join(", ")}</small>
                          <div className="pdf-hub__answer-panel">
                            <label htmlFor={`answer-${concept.id}`}>
                              Explain this concept in your own words and give an example.
                            </label>
                            <textarea
                              id={`answer-${concept.id}`}
                              rows={5}
                              maxLength={4000}
                              value={answer}
                              disabled={busy !== null}
                              onChange={(event) => {
                                setAnswer(event.target.value);
                                setFeedback(null);
                              }}
                            />
                            <div className="pdf-hub__answer-actions">
                              <button
                                type="button"
                                disabled={busy !== null || !answer.trim()}
                                onClick={() => void submitAnswer()}
                              >
                                {busy === "assess" ? "Reviewing..." : "Review my explanation"}
                              </button>
                            </div>
                          </div>
                          {feedback && (
                            <section className="pdf-hub__feedback" aria-labelledby={`feedback-title-${concept.id}`}>
                              <h5 id={`feedback-title-${concept.id}`}>Your feedback</h5>
                              <MarkdownText value={feedback.feedback} />
                              {feedback.likely_gaps.length > 0 && (
                                <>
                                  <h5>Ideas to revisit</h5>
                                  <ul>{feedback.likely_gaps.map((gap, index) => (
                                    <li key={index}><MarkdownText value={gap} /></li>
                                  ))}</ul>
                                </>
                              )}
                              <p><strong>Think about this:</strong></p>
                              <MarkdownText value={feedback.next_question} />
                              <small>Feedback sources: {feedback.sources.join(", ")}</small>
                            </section>
                          )}
                        </section>
                      )}
                    </article>
                  ))}
                </>
              )}
            </>
          )}
          <button type="button" disabled={busy !== null} onClick={() => void refreshDocument()}>
            {busy === "refresh" ? "Refreshing..." : "Refresh status"}
          </button>
          <button type="button" disabled={busy !== null} onClick={clearDocument}>
            Clear selection
          </button>
        </section>
      )}
    </section>
  );
}

export default PdfHub;
