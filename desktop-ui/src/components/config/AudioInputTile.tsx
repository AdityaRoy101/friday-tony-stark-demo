import { useState, useEffect } from 'react';

export default function AudioInputTile() {
  const [hasAudio, setHasAudio] = useState(false);
  const [volume, setVolume] = useState(0);

  useEffect(() => {
    let animationFrame: number;

    const updateVolume = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        const microphone = audioContext.createMediaStreamSource(stream);
        microphone.connect(analyser);
        analyser.fftSize = 256;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        const tick = () => {
          analyser.getByteFrequencyData(dataArray);
          const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
          setVolume(avg / 255);
          animationFrame = requestAnimationFrame(tick);
        };
        tick();
        setHasAudio(true);

        return () => {
          cancelAnimationFrame(animationFrame);
          stream.getTracks().forEach((t) => t.stop());
          audioContext.close();
        };
      } catch {
        setHasAudio(false);
      }
    };

    const cleanup = updateVolume();
    return () => {
      cleanup.then((fn) => fn && fn());
    };
  }, []);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex items-end gap-1 h-16">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="w-3 bg-zinc-700 rounded-t transition-all duration-100"
            style={{
              height: hasAudio ? `${volume * 100 * (0.5 + i * 0.15)}%` : '10%',
            }}
          />
        ))}
      </div>
      {!hasAudio && (
        <span className="ml-3 text-xs text-zinc-500">No mic</span>
      )}
    </div>
  );
}