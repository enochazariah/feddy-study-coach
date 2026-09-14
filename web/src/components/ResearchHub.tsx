import { useEffect, useRef, useState } from "react";
import { ApiError, apiClient } from "../api/client";
import "../styles/research-hub.css";

type Source = {
  title: string;
  summary: string;
  url: string;
  source: string;
  fullUrl: string;
};

type Video = { id: string; title: string; thumbnail: string };

function safeMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.status === 429) {
    return "Too many requests. Please try again later.";
  }
  return error instanceof ApiError ? error.message : fallback;
}

function asSafeSource(resource: {
  title: string;
  summary: string;
  url: string;
  source: string;
}): Source | null {
  try {
    const parsed = new URL(resource.url);
    if (!/^https?:$/.test(parsed.protocol)) return null;
    return { ...resource, fullUrl: parsed.toString() };
  } catch {
    return null;
  }
}

function asSafeVideo(video: Video): Video | null {
  if (!/^[A-Za-z0-9_-]{11}$/.test(video.id) || !video.title) return null;
  if (!video.thumbnail) return video;
  try {
    const parsed = new URL(video.thumbnail);
    if (!/^https?:$/.test(parsed.protocol)) return { ...video, thumbnail: "" };
  } catch {
    return { ...video, thumbnail: "" };
  }
  return video;
}

export function ResearchHub() {
  const [topic, setTopic] = useState("");
  const [resources, setResources] = useState<Source[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [readingState, setReadingState] = useState<"idle" | "loading" | "ready" | "empty" | "error">("idle");
  const [videoState, setVideoState] = useState<"idle" | "loading" | "ready" | "empty" | "error">("idle");
  const [readingError, setReadingError] = useState("");
  const [videoError, setVideoError] = useState("");
  const [brokenThumbnails, setBrokenThumbnails] = useState<Record<string, boolean>>({});
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [searching, setSearching] = useState(false);
  const searchActive = useRef(false);

  useEffect(() => {
    if (!activeSource) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActiveSource(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [activeSource]);

  async function search() {
    const query = topic.trim();
    if (!query || searchActive.current) return;
    searchActive.current = true;
    setSearching(true);
    setReadingState("loading");
    setVideoState("loading");
    setReadingError("");
    setVideoError("");

    const readingRequest = apiClient.searchResources(query)
      .then((result) => {
        const items = Array.isArray(result.resources) ? result.resources : [];
        const safeItems = items.map(asSafeSource).filter((item): item is Source => Boolean(item));
        setResources(safeItems);
        setReadingState(safeItems.length ? "ready" : "empty");
      })
      .catch((failure: unknown) => {
        setResources([]);
        setReadingState("error");
        setReadingError(safeMessage(failure, "Reading search is temporarily unavailable."));
      });

    const videoRequest = apiClient.searchVideos(query)
      .then((result) => {
        const items = Array.isArray(result.videos)
          ? result.videos.filter((video) => video && video.id && video.title)
          : [];
        const safeItems = items.map(asSafeVideo).filter((item): item is Video => Boolean(item));
        setVideos(safeItems);
        setSelectedVideo(null);
        setVideoState(safeItems.length ? "ready" : "empty");
      })
      .catch((failure: unknown) => {
        setVideos([]);
        setVideoState("error");
        setVideoError(safeMessage(failure, "Video search is temporarily unavailable."));
      });

    await Promise.allSettled([readingRequest, videoRequest]);
    searchActive.current = false;
    setSearching(false);
  }

  const hasSearch = readingState !== "idle" || videoState !== "idle";

  return (
    <section className="hub-panel research-hub">
      <div className="hub-panel__heading">
        <div>
          <p className="hub-eyebrow">Explore beyond the lesson</p>
          <h2>Research &amp; videos</h2>
        </div>
        <span className="hub-badge">Correlated</span>
      </div>
      <form className="research-search" onSubmit={(event) => { event.preventDefault(); void search(); }}>
        <label htmlFor="research-topic">Search by topic</label>
        <div className="research-search__controls">
          <input
            id="research-topic"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="e.g. gradient descent"
            maxLength={200}
          />
          <button className="btn-primary" disabled={searching || !topic.trim()}>
            {searching ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      {hasSearch && (
        <div className="research-grid">
          <section className="research-column" aria-labelledby="reading-title">
            <div className="research-column__heading">
              <div>
                <p className="research-column__eyebrow">Read next</p>
                <h3 id="reading-title">Reading</h3>
              </div>
              {readingState === "loading" && <span role="status">Searching...</span>}
            </div>
            {readingState === "error" && <p className="hub-message" role="alert">{readingError}</p>}
            {readingState === "empty" && <p className="hub-empty">No reading resources found for this topic.</p>}
            {readingState === "ready" && resources.map((resource) => (
              <article className="source-card" key={resource.fullUrl}>
                <button className="source-card__open" type="button" onClick={() => setActiveSource(resource)}>
                  <span>{resource.source}</span>
                  <strong>{resource.title}</strong>
                  <p>{resource.summary}</p>
                </button>
                <a href={resource.fullUrl} target="_blank" rel="noopener noreferrer">Read resource</a>
              </article>
            ))}
          </section>

          <section className="research-column" aria-labelledby="videos-title">
            <div className="research-column__heading">
              <div>
                <p className="research-column__eyebrow">Watch and review</p>
                <h3 id="videos-title">Videos</h3>
              </div>
              {videoState === "loading" && <span role="status">Searching...</span>}
            </div>
            {videoState === "error" && <p className="hub-message" role="alert">{videoError}</p>}
            {videoState === "empty" && <p className="hub-empty">No videos found for this topic.</p>}
            {videoState === "ready" && (
              <>
                {selectedVideo && (
                  <section className="video-player" aria-labelledby="selected-video-title">
                    <div className="video-player__heading">
                      <h4 id="selected-video-title">{selectedVideo.title}</h4>
                      <button type="button" onClick={() => setSelectedVideo(null)}>Close</button>
                    </div>
                    <div className="video-player__frame">
                      <iframe
                        title={selectedVideo.title}
                        src={`https://www.youtube-nocookie.com/embed/${selectedVideo.id}?controls=1&fs=1`}
                        allow="encrypted-media; fullscreen"
                        allowFullScreen
                      />
                    </div>
                    <a
                      className="video-player__fallback"
                      href={`https://www.youtube.com/watch?v=${encodeURIComponent(selectedVideo.id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Open on YouTube if playback is unavailable
                    </a>
                  </section>
                )}
                <div className="video-grid">
                {videos.map((video) => (
                  <article className="video-card" key={video.id}>
                    <button className="video-card__watch" type="button" onClick={() => setSelectedVideo(video)}>
                      {video.thumbnail && !brokenThumbnails[video.id] ? (
                        <img
                          src={video.thumbnail}
                          alt=""
                          loading="lazy"
                          onError={() => setBrokenThumbnails((current) => ({ ...current, [video.id]: true }))}
                        />
                      ) : (
                        <span className="video-card__fallback" aria-label="Video thumbnail unavailable">Thumbnail unavailable</span>
                      )}
                      <strong>{video.title}</strong>
                      <span>Watch here.</span>
                    </button>
                    <a
                      className="video-card__external"
                      href={`https://www.youtube.com/watch?v=${encodeURIComponent(video.id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Open on YouTube
                    </a>
                  </article>
                ))}
                </div>
              </>
            )}
          </section>
        </div>
      )}

      {activeSource && <div className="reader-modal" role="dialog" aria-modal="true" aria-labelledby="reader-title">
        <div className="reader-modal__bar">
          <strong id="reader-title">{activeSource.title}</strong>
          <div>
            <a href={activeSource.fullUrl} target="_blank" rel="noopener noreferrer">Read resource</a>
            <button type="button" onClick={() => setActiveSource(null)}>Close</button>
          </div>
        </div>
        <iframe title={`Reading ${activeSource.title}`} src={activeSource.fullUrl} sandbox="allow-scripts allow-same-origin" />
      </div>}
    </section>
  );
}

export default ResearchHub;
