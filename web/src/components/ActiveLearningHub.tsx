import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import { apiClient, getApiErrorMessage } from "../api/client";
import type { QuizQuestion } from "../api/client";
import "../styles/active-learning.css";

// QUIZ_REVIEW_FLOW_V1
type Evaluation = { score: number; feedback: string };
type QuizConfig = { topic: string; count: number; type: string };

function FeedbackMarkdown({ value }: { value: string }) {
  return (
    <div className="quiz-feedback__markdown">
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

function QuizText({ value }: { value: string }) {
  return (
    <ReactMarkdown
      skipHtml
      components={{
        p: ({ children }) => <span>{children}</span>,
      }}
    >
      {value}
    </ReactMarkdown>
  );
}

export function ActiveLearningHub() {
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [type, setType] = useState("multiple_choice");
  const [activeConfig, setActiveConfig] = useState<QuizConfig | null>(null);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [evaluations, setEvaluations] = useState<Record<number, Evaluation>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [gradingIndex, setGradingIndex] = useState<number | null>(null);
  const [finished, setFinished] = useState(false);
  const [editingConfig, setEditingConfig] = useState(true);
  const [error, setError] = useState("");
  const operationActive = useRef(false);
  const requestVersion = useRef(0);
  const topicInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => { requestVersion.current += 1; };
  }, []);

  const busy = isLoading || gradingIndex !== null;
  const gradedCount = Object.keys(evaluations).length;
  const unansweredCount = questions.filter(
    (_, index) => !answers[index]?.trim()
  ).length;
  const pendingCount = questions.filter(
    (_, index) => answers[index]?.trim() && !evaluations[index]
  ).length;
  const average = gradedCount
    ? Math.round(Object.values(evaluations).reduce(
        (sum, result) => sum + result.score, 0
      ) / gradedCount)
    : null;

  async function generateSet(config: QuizConfig) {
    if (operationActive.current) return;
    if (!config.topic.trim()) {
      setError("Please enter a topic.");
      return;
    }
    operationActive.current = true;
    const version = ++requestVersion.current;
    setIsLoading(true);
    setError("");
    try {
      const excludedQuestions: string[] = [];
      let excludedCharacters = 0;
      if (activeConfig?.topic.toLowerCase() === config.topic.trim().toLowerCase()) {
        for (const item of questions) {
          if (excludedQuestions.length >= 50) break;
          if (excludedCharacters + item.question.length > 30000) continue;
          excludedQuestions.push(item.question);
          excludedCharacters += item.question.length;
        }
      }
      const result = await apiClient.generateQuiz(
        config.topic.trim(), config.count, config.type, excludedQuestions
      );
      if (version !== requestVersion.current) return;
      if (!Array.isArray(result.questions) || !result.questions.length) {
        throw new Error("No questions returned.");
      }
      // Replace the previous set only after successful generation.
      setQuestions(result.questions);
      setAnswers({});
      setEvaluations({});
      setFinished(false);
      setEditingConfig(false);
      setActiveConfig({ ...config, topic: config.topic.trim() });
    } catch (failure) {
      if (version === requestVersion.current) {
        setError(getApiErrorMessage(
          failure, "Could not generate a new set. Your current answers are preserved."
        ));
      }
    } finally {
      operationActive.current = false;
      if (version === requestVersion.current) setIsLoading(false);
    }
  }

  function createQuiz(event: FormEvent) {
    event.preventDefault();
    void generateSet({ topic, count, type });
  }

  async function submitAnswer(index: number) {
    const item = questions[index];
    const answer = answers[index]?.trim();
    if (
      operationActive.current || finished || evaluations[index]
      || !answer || !item?.evaluation_token
    ) return;
    operationActive.current = true;
    const version = ++requestVersion.current;
    setGradingIndex(index);
    setError("");
    try {
      const result = await apiClient.evaluateTheoryResponse(
        answer, item.evaluation_token
      );
      if (version === requestVersion.current) {
        setEvaluations((current) => ({ ...current, [index]: result }));
      }
    } catch (failure) {
      if (version === requestVersion.current) {
        setError(getApiErrorMessage(
          failure, "Could not grade this answer. Please try again."
        ));
      }
    } finally {
      operationActive.current = false;
      if (version === requestVersion.current) setGradingIndex(null);
    }
  }

  return (
    <section className="hub-panel active-learning">
      <div className="hub-panel__heading">
        <div>
          <p className="hub-eyebrow">Explain, practise, reflect</p>
          <h2>Active recall</h2>
        </div>
        <span className="hub-badge">Practice</span>
      </div>

      {editingConfig && (
        <form className="quiz-config" onSubmit={createQuiz}>
          <label>Topic
            <input
              ref={topicInput}
              value={topic}
              required
              maxLength={200}
              placeholder={type === "theory"
                ? "Enter a topic to practise explaining"
                : "Enter a topic to test your knowledge"}
              disabled={busy}
              onChange={(event) => setTopic(event.target.value)}
            />
          </label>
          <label>Questions
            <select value={count} disabled={busy}
              onChange={(event) => setCount(Number(event.target.value))}>
              {Array.from({ length: 50 }, (_, index) => index + 1).map(
                (value) => <option value={value} key={value}>{value}</option>
              )}
            </select>
          </label>
          <label>Type
            <select value={type} disabled={busy}
              onChange={(event) => setType(event.target.value)}>
              <option value="multiple_choice">Multiple choice</option>
              <option value="theory">Theory</option>
            </select>
          </label>
          <button className="btn-primary" disabled={busy || !topic.trim()}>
            {isLoading ? "Building..." : questions.length ? "Generate replacement set" : "Generate quiz"}
          </button>
          {questions.length > 0 && (
            <>
              <p>Your current set stays available until a replacement succeeds.</p>
              <button type="button" disabled={busy}
                onClick={() => setEditingConfig(false)}>Keep current set</button>
            </>
          )}
        </form>
      )}

      {error && <p className="hub-message" role="alert">{error}</p>}
      {activeConfig && <h3>Current topic: {activeConfig.topic}</h3>}
      {isLoading && <p role="status">Generating your question set...</p>}

      {finished && (
        <section className="quiz-review" aria-label="Quiz review" aria-live="polite">
          <h3>Set review</h3>
          <p>{gradedCount} of {questions.length} questions graded.</p>
          <p>{unansweredCount} unanswered; {pendingCount} answered but not graded.</p>
          <p>{average === null
            ? "No graded answers yet."
            : `Average across graded answers: ${average}/100.`}</p>
          <p>Review the feedback below. This score is evidence from this set, not a guarantee of mastery.</p>
        </section>
      )}

      <div className="quiz-list">
        {questions.map((item, index) => {
          const result = evaluations[index];
          const locked = busy || finished || Boolean(result);
          return (
            <article className="quiz-card" key={`${item.question}-${index}`}>
              <span className="quiz-number">{String(index + 1).padStart(2, "0")}</span>
              <h3><QuizText value={item.question} /></h3>
              {item.options?.length ? item.options.map((option, optionIndex) => (
                <label className="quiz-option" key={`${optionIndex}-${option}`}>
                  <input type="radio" name={`question-${index}`}
                    value={option}
                    checked={answers[index] === option}
                    disabled={locked}
                    onChange={(event) => setAnswers((current) => ({
                      ...current, [index]: event.target.value,
                    }))}
                  />
                  <span className="quiz-option__text"><QuizText value={option} /></span>
                </label>
              )) : (
                <textarea rows={5} maxLength={6000}
                  value={answers[index] || ""}
                  disabled={locked}
                  aria-label={`Response to question ${index + 1}`}
                  placeholder="Explain your reasoning"
                  onChange={(event) => setAnswers((current) => ({
                    ...current, [index]: event.target.value,
                  }))}
                />
              )}
              {!finished && (
                <button type="button" className="btn-primary"
                  disabled={locked || !answers[index]?.trim() || !item.evaluation_token}
                  onClick={() => void submitAnswer(index)}>
                  {gradingIndex === index ? "Reviewing..." : result ? "Submitted" : "Submit answer"}
                </button>
              )}
              {result ? (
                <div className="quiz-review">
                  <p><strong>Score: {result.score}/100</strong></p>
                  <section className="quiz-feedback" aria-label="Answer feedback">
                    <h4>Feedback</h4>
                    <FeedbackMarkdown value={result.feedback} />
                  </section>
                </div>
              ) : finished && (
                <p>{answers[index]?.trim() ? "Answered, but not graded." : "Unanswered."}</p>
              )}
            </article>
          );
        })}
      </div>

      {questions.length > 0 && (
        <div className="quiz-actions">
          <button type="button" className="btn-primary" disabled={busy}
            onClick={() => setFinished((current) => !current)}>
            {finished ? "Continue answering" : "Finish & review"}
          </button>
          {finished && activeConfig && (
            <>
              <button type="button" disabled={busy}
                onClick={() => void generateSet(activeConfig)}>
                {isLoading ? "Generating..." : "Generate another set"}
              </button>
              <button type="button" disabled={busy} onClick={() => {
                setEditingConfig(true);
                setTimeout(() => topicInput.current?.focus(), 0);
              }}>
                Change topic
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
