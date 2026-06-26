"use client";

import { useState, useEffect } from "react";

interface Topic {
  id: number;
  name: string;
  mastery_level: number;
  num_attempts: number;
}

interface Question {
  id: number;
  type: string;
  prompt: string;
  options?: string[];
}

interface QuizModalProps {
  topic: Topic;
  isOpen: boolean;
  onClose: () => void;
}

export default function QuizModal({ topic, isOpen, onClose }: QuizModalProps) {
  const [quiz, setQuiz] = useState<{
    quiz_id: number;
    questions: Question[];
  } | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answers, setAnswers] = useState<{ [key: number]: string }>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    is_correct: boolean;
    correct_answer: string;
    explanation: string;
    mastery_level: number;
  } | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5000";

  useEffect(() => {
    if (!isOpen) return;

    const generateQuiz = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `${apiUrl}/quizzes/generate?topic_id=${topic.id}&num_questions=3`
        );
        const data = await response.json();
        setQuiz(data);
        setCurrentQuestion(0);
        setAnswers({});
        setResult(null);
      } catch (error) {
        console.error("Failed to generate quiz:", error);
      } finally {
        setLoading(false);
      }
    };

    generateQuiz();
  }, [isOpen, topic.id, apiUrl]);

  const submitAnswer = async () => {
    if (!quiz) return;

    const question = quiz.questions[currentQuestion];
    const userAnswer = answers[question.id];

    if (!userAnswer) {
      alert("Please select or enter an answer");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `${apiUrl}/quizzes/${quiz.quiz_id}/submit?question_id=${question.id}&user_response=${encodeURIComponent(userAnswer)}&confidence=0.7`,
        { method: "POST" }
      );
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error("Failed to submit answer:", error);
    } finally {
      setLoading(false);
    }
  };

  const nextQuestion = () => {
    if (!quiz) return;
    if (currentQuestion < quiz.questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setResult(null);
    } else {
      onClose();
    }
  };

  if (!isOpen) return null;

  if (loading && !quiz) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-slate-800 p-6 rounded-lg text-white">
          <p>Generating quiz on {topic.name}...</p>
        </div>
      </div>
    );
  }

  if (!quiz || !quiz.questions || quiz.questions.length === 0) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-slate-800 p-6 rounded-lg text-white">
          <p>Error loading quiz. Please try again.</p>
          <button onClick={onClose} className="mt-4 px-4 py-2 bg-blue-600 rounded">
            Close
          </button>
        </div>
      </div>
    );
  }

  const question = quiz.questions[currentQuestion];
  if (!question) return null;

  const isAnswered = result !== null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-lg p-6 max-w-2xl w-full text-white max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold">{topic.name} Quiz</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl"
          >
            ✕
          </button>
        </div>

        {/* Progress */}
        <div className="mb-6">
          <div className="flex justify-between text-sm text-gray-400 mb-2">
            <span>
              Question {currentQuestion + 1} of {quiz.questions.length}
            </span>
            <span>{Math.round(((currentQuestion + 1) / quiz.questions.length) * 100)}%</span>
          </div>
          <div className="bg-slate-700 h-2 rounded overflow-hidden">
            <div
              className="bg-blue-500 h-full transition-all"
              style={{
                width: `${((currentQuestion + 1) / quiz.questions.length) * 100}%`,
              }}
            />
          </div>
        </div>

        {/* Question */}
        <div className="mb-6">
          <p className="text-lg font-medium mb-4">{question.prompt}</p>

          {question.type === "multiple_choice" && question.options && (
            <div className="space-y-2">
              {question.options.map((option, idx) => {
                const letter = String.fromCharCode(65 + idx); // A, B, C, D
                const isSelected = answers[question.id] === letter;

                return (
                  <button
                    key={idx}
                    onClick={() =>
                      setAnswers({
                        ...answers,
                        [question.id]: letter,
                      })
                    }
                    disabled={isAnswered}
                    className={`w-full p-3 text-left rounded transition ${
                      isSelected
                        ? "bg-blue-600 border border-blue-400"
                        : "bg-slate-700 border border-slate-600 hover:border-slate-500"
                    } ${isAnswered ? "opacity-50" : ""}`}
                  >
                    {option}
                  </button>
                );
              })}
            </div>
          )}

          {question.type === "true_false" && (
            <div className="flex gap-3">
              {["true", "false"].map((option) => (
                <button
                  key={option}
                  onClick={() =>
                    setAnswers({
                      ...answers,
                      [question.id]: option,
                    })
                  }
                  disabled={isAnswered}
                  className={`flex-1 p-3 rounded transition capitalize ${
                    answers[question.id] === option
                      ? "bg-blue-600 border border-blue-400"
                      : "bg-slate-700 border border-slate-600 hover:border-slate-500"
                  } ${isAnswered ? "opacity-50" : ""}`}
                >
                  {option}
                </button>
              ))}
            </div>
          )}

          {question.type === "short_answer" && (
            <input
              type="text"
              value={answers[question.id] ?? ""}
              onChange={(e) =>
                setAnswers({
                  ...answers,
                  [question.id]: e.target.value,
                })
              }
              disabled={isAnswered}
              placeholder="Type your answer..."
              className="w-full p-3 bg-slate-700 border border-slate-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          )}
        </div>

        {/* Result feedback */}
        {result && (
          <div
            className={`p-4 rounded mb-6 ${
              result.is_correct
                ? "bg-green-500/20 border border-green-500"
                : "bg-red-500/20 border border-red-500"
            }`}
          >
            <p className="font-semibold mb-2">
              {result.is_correct ? "✓ Correct!" : "✗ Incorrect"}
            </p>
            {!result.is_correct && (
              <p className="text-sm text-gray-300 mb-2">
                Correct answer: {result.correct_answer}
              </p>
            )}
            {result.explanation && (
              <p className="text-sm text-gray-300">{result.explanation}</p>
            )}
            <p className="text-xs text-gray-400 mt-2">
              Topic mastery: {Math.round(result.mastery_level * 100)}%
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          {!isAnswered ? (
            <button
              onClick={submitAnswer}
              disabled={loading}
              className="flex-1 p-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 rounded font-medium transition"
            >
              Submit Answer
            </button>
          ) : (
            <button
              onClick={nextQuestion}
              className="flex-1 p-3 bg-blue-600 hover:bg-blue-700 rounded font-medium transition"
            >
              {currentQuestion < quiz.questions.length - 1
                ? "Next Question"
                : "Close"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
