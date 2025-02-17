const TranscriptResults = ({ transcript, onDownload }) => {
  console.log(transcript)
  // Add this to check the structure
  if (transcript?.transcripts) {
      console.log('Multiple transcripts found:', transcript.transcripts);
  }

  // Handle multiple transcripts
  if (transcript?.status === 'success' && transcript.transcripts) {
    console.log(transcript.transcripts)    
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
            {transcript.transcripts.map((item, index) => {    // Changed from transcript.transcript.map
              console.log('Full item data:', item);  // Let's see what's in the item
              console.log('Item path:', item.path);
              
              const filename = item.filename || item.path?.split(/[/\\]/).pop();
              console.log('Derived filename:', filename);

              return (
                <div key={index} className="border rounded p-4">
                  <h3 className="font-medium mb-2">{item.title}</h3>
                  <div className="text-sm text-gray-600 mb-3">
                    {item.text.substring(0, 150)}...
                  </div>
                  <button
                    onClick={() => {
                      console.log('path:',item)
                      console.log('Download clicked for:', item.filename);
                      onDownload(item.filename);
                    }}
                    className="bg-blue-500 text-white py-1 px-3 rounded text-sm hover:bg-blue-600 transition-colors"
                  >
                    Download Transcript
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // Handle single transcript
  if (transcript?.status === 'success' && transcript.transcript) {
    console.log('Handling single transcript:', transcript);
    // Get filename from either direct filename property or from transcript_path
    const filename = transcript.filename || transcript.transcript_path?.split(/[/\\]/).pop();
    console.log('Using filename:', filename);
    


    return (
      <div className="border rounded-lg p-6 shadow-sm mt-4">
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 text-green-800 rounded p-4">
            <div className="font-medium">Success</div>
            <div>Transcription completed successfully!</div>
          </div>

          <div className="mt-4 p-4 bg-gray-50 rounded text-sm">
            {transcript.transcript?.substring(0, 350)}...
          </div>
          <button
            onClick={() => {
              console.log('Download clicked for:', filename);
              if (filename) {
                onDownload(filename);
              } else {
                console.error('No filename available for download');
              }
            }}
            className="w-full bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600 transition-colors"
          >
            Download Transcript
          </button>
        </div>
      </div>
    );
  }
  console.log('No matching condition found for transcript:', transcript);

  return null;
};

export default TranscriptResults;