"use client";

import { useEffect, useState } from "react";
import QuizModal from "./QuizModal";

interface Topic {
  id: number;
  name: string;
  mastery_level: number;
  num_attempts: number;
}

export default function TopicsList() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);
  const [showQuizModal, setShowQuizModal] = useState(false);

  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5000"}/topics`
        );
        const data = await response.json();
        setTopics(data);
      } catch (error) {
        console.error("Failed to fetch topics:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchTopics();
    const interval = setInterval(fetchTopics, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const getMasteryColor = (level: number) => {
    if (level >= 0.85) return "bg-green-500";
    if (level >= 0.7) return "bg-blue-500";
    if (level >= 0.5) return "bg-yellow-500";
    return "bg-gray-400";
  };

  const handleGenerateQuiz = (topic: Topic) => {
    setSelectedTopic(topic);
    setShowQuizModal(true);
  };

  if (loading) {
    return <div className="text-gray-400">Loading topics...</div>;
  }

  if (topics.length === 0) {
    return (
      <div className="text-gray-400 text-sm">
        Upload a PDF to see topics extracted automatically
      </div>
    );
  }

  return (
    <>
      <div className="space-y-2">
        {topics.map((topic) => (
          <div
            key={topic.id}
            className="p-3 bg-slate-700/50 rounded border border-slate-600 hover:border-slate-500 transition"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">{topic.name}</span>
              <span className="text-xs text-gray-400">
                {topic.num_attempts} attempts
              </span>
            </div>

            {/* Mastery bar */}
            <div className="w-full bg-slate-600 rounded h-2 mb-3 overflow-hidden">
              <div
                className={`h-full transition-all ${getMasteryColor(
                  topic.mastery_level
                )}`}
                style={{ width: `${topic.mastery_level * 100}%` }}
              />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-300">
                {Math.round(topic.mastery_level * 100)}% mastered
              </span>
              <button
                onClick={() => handleGenerateQuiz(topic)}
                className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded transition"
              >
                📝 Quiz
              </button>
            </div>
          </div>
        ))}
      </div>

      {selectedTopic && (
        <QuizModal
          topic={selectedTopic}
          isOpen={showQuizModal}
          onClose={() => {
            setShowQuizModal(false);
            setSelectedTopic(null);
          }}
        />
      )}
    </>
  );
}
