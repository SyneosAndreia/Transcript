import React from 'react';

const TranscriptResults = ({ transcript, onDownload }) => {
  // Handle single transcript
  if (transcript && !transcript.transcripts) {
    return (
      <div className="border rounded-lg p-6 shadow-sm">
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 text-green-800 rounded p-4">
            <div className="font-medium">Success</div>
            <div>Transcription completed successfully!</div>
          </div>
          
          <button
            onClick={() => onDownload(transcript.filename)}
            className="w-full bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600 transition-colors"
          >
            Download Transcript
          </button>

          <div className="mt-4 p-4 bg-gray-50 rounded text-sm">
            {transcript.transcript}
          </div>
        </div>
      </div>
    );
  }

  // Handle playlist transcripts
  if (transcript?.transcripts) {
    return (
      <div className="border rounded-lg p-6 shadow-sm">
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 text-green-800 rounded p-4">
            <div className="font-medium">Success</div>
            <div>
              Playlist transcription completed! {transcript.transcripts.length} videos processed.
            </div>
          </div>

          <div className="space-y-4">
            {transcript.transcripts.map((item, index) => (
              <div key={index} className="border rounded p-4">
                <h3 className="font-medium mb-2">{item.title}</h3>
                <div className="text-sm text-gray-600 mb-3">{item.text.substring(0, 150)}...</div>
                <button
                  onClick={() => {
                    const filename = item.path.split('\\').pop(); // Extract filename from path
                    onDownload(filename);
                  }}
                  className="bg-blue-500 text-white py-1 px-3 rounded text-sm hover:bg-blue-600 transition-colors"
                >
                  Download Transcript
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default TranscriptResults;