// Uses the Vite environment variable if set, otherwise defaults to local Django server
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export interface AppUser {
  id: string;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
}

interface Subject { id: string; slug: string; name: string }
interface Topic { id: string; slug: string; name: string }

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Too many requests, please slow down.";
    if (error.status === 503) return "Grading is temporarily unavailable. Your answer is preserved; please try again.";
    if (error.status === 500 || error.status === 504) return "AI model is busy, please try again.";
  }
  return fallback;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('feddy_session_token');
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(errorData.error || `Server error: ${response.status}`, response.status);
  }

  return response.json() as Promise<T>;
}


export interface DocumentConcept {
  id: string;
  title: string;
  description: string;
  supporting_chunk_ids: number[];
  pages: number[];
}

export interface DocumentAnalysis {
  overview: string;
  concepts: DocumentConcept[];
  analysis_version: string;
  coverage: {
    chunk_ids: number[];
    pages: number[];
    extraction_status: "ready" | "partial" | "failed";
    scope: string;
  };
}

export interface StudyDocumentDetail {
  documentId: string;
  filename: string;
  extractionStatus: "ready" | "partial" | "failed";
  pagesProcessed: number;
  totalPages: number;
  analysisStatus: "pending" | "processing" | "ready" | "failed";
  analysis: DocumentAnalysis | null;
  analysisError: string;
}

export type DocumentAnalysisResponse =
  | {
      documentId: string;
      analysisStatus: "ready";
      analysis: DocumentAnalysis;
      reused: boolean;
    }
  | {
      documentId: string;
      analysisStatus: "processing";
    };

export const apiClient = {
  async assessConceptAnswer(
    documentId: string, topicId: string, answer: string
  ): Promise<{
    topicId: string;
    feedback: string;
    likely_gaps: string[];
    next_question: string;
    sources: number[];
  }> {
    return request(`/tutor/documents/${encodeURIComponent(documentId)}/assess/`, {
      method: "POST",
      body: JSON.stringify({ topicId, answer }),
    });
  },

  async generateConceptLesson(documentId: string, topicId: string): Promise<{
    topicId: string;
    lesson: {
      explanation: string;
      example: string;
      key_ideas: string[];
      questions: string[];
      sources: number[];
    };
  }> {
    return request(`/tutor/documents/${encodeURIComponent(documentId)}/lesson/`, {
      method: "POST",
      body: JSON.stringify({ topicId }),
    });
  },


  async getDocument(documentId: string): Promise<StudyDocumentDetail> {
    return request(`/tutor/documents/${encodeURIComponent(documentId)}/`);
  },

  async analyzeDocument(documentId: string): Promise<DocumentAnalysisResponse> {
    return request(`/tutor/documents/${encodeURIComponent(documentId)}/analyze/`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  },


  async me(): Promise<{ user: AppUser }> {
    return request('/accounts/me');
  },

  async signInWithGoogle(idToken: string): Promise<{ token: string; user: AppUser }> {
    return request('/accounts/google', {
      method: 'POST',
      body: JSON.stringify({ id_token: idToken }),
    });
  },

  async demoLogin(email: string): Promise<{ token: string; user: AppUser }> {
    return request('/accounts/demo-login/', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  },

  async subjects(): Promise<{ subjects: Subject[] }> {
    return request('/subjects');
  },

  async topics(subjectId: string): Promise<{ topics: Topic[] }> {
    return request(`/subjects/${subjectId}/topics`);
  },

  async uploadDocument(file: File): Promise<{
    status: string;
    documentId: string;
    extractionStatus: "ready" | "partial" | "failed";
    filename: string;
    size: number;
    textPreview: string;
    overview: string;
    topics: Array<{ title: string; description: string; pages: number[]; chunk_indexes: number[] }>;
    storedPath: string;
  }> {
    const token = localStorage.getItem('feddy_session_token');
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE_URL}/tutor/upload/`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ApiError(errorData.error || `Server error: ${response.status}`, response.status);
    }
    return response.json();
  },

  async generateDocumentLesson(documentId: string, topic: string): Promise<{
    topic: string;
    documentStatus: "ready" | "partial" | "failed";
    lesson: { explanation: string; example: string; key_ideas: string[]; questions: string[]; sources: number[] };
  }> {
    return request(`/tutor/documents/${documentId}/lesson/`, {
      method: "POST",
      body: JSON.stringify({ topic }),
    });
  },

  async searchResources(topic: string): Promise<{ resources: Array<{ title: string; summary: string; url: string; source: string }> }> {
    return request(`/tutor/search/?topic=${encodeURIComponent(topic)}`);
  },

  async searchVideos(topic: string): Promise<{ videos: Array<{ id: string; title: string; thumbnail: string }> }> {
    return request(`/tutor/videos/?topic=${encodeURIComponent(topic)}`);
  },

  async generateQuiz(topic: string, numQuestions: number, questionType: string, excludedQuestions: string[] = []): Promise<{ questions: QuizQuestion[] }> {
    return request('/active-learning/generate/', {
      method: 'POST',
      body: JSON.stringify({ topic, num_questions: numQuestions, question_type: questionType, exclude_questions: excludedQuestions }),
    });
  },

  async evaluateTheoryResponse(response: string, evaluationToken: string): Promise<{ score: number; feedback: string }> {
    return request('/tutor/active-learning/evaluate/', {
      method: 'POST',
      body: JSON.stringify({ response, evaluation_token: evaluationToken }),
    });
  },

  /**
   * Sends a message to the Feddy Study Coach backend and returns the response.
   */
  async chatWithTutor(message: string, history: Array<{ role: 'user' | 'assistant'; content: string }> = [], context = ""): Promise<string> {
    try {
      const response = await fetch(`${API_BASE_URL}/tutoring/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(localStorage.getItem('feddy_session_token')
            ? { Authorization: `Bearer ${localStorage.getItem('feddy_session_token')}` }
            : {}),
        },
        body: JSON.stringify({ message, history, context, document_id: localStorage.getItem("feddy_document_id") || "" }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(errorData.error || `Server error: ${response.status}`, response.status);
      }

      const data = await response.json();
      return data.response;
      
    } catch (error) {
      console.error("Failed to communicate with Feddy:", error);
      throw error;
    }
  }
};

export interface QuizQuestion {
  question: string;
  options?: string[];
  answer?: string;
  explanation?: string;
  rubric?: string;
  model_answer?: string;
  evaluation_token?: string;
}

export const api = apiClient;