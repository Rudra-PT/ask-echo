import React from 'react';

const PIXEL_MAP = [
  "....XXXXXXXX....",
  "..XXWWWWWWWWXX..",
  ".XWWWWWWWWWWWWX.",
  "XHHWWWWWWWWWWHHX",
  "XHGWWWWWWWWWWGHX",
  "XHHWKKWWWWKKWHHX",
  "XWWKGGKWWKGGKWWX",
  "XWWKGGKWWKGGKWWX",
  "XWWWKKWWWWKKWWWX",
  "XWWWWWWWWWWWWWWX",
  ".XWWWWKKKKWWWWX.",
  ".XWWWWGGGGWWWWX.",
  "..XWWWWWWWWWWX..",
  "...XXWWWWWWXX...",
  ".....XXXXXX....."
];

export function EchoEchoLogo({ className, size = 36 }) {
  const colors = {
    'X': '#111111', 
    'W': '#E6E8EA', 
    'H': '#6A7B8C', 
    'G': '#39FF14', 
    'K': '#1B1E24', 
  };

  return (
    <svg 
      className={className} 
      width={size} 
      height={size} 
      viewBox="0 0 16 15" 
      style={{ shapeRendering: 'crispEdges', display: 'inline-block', verticalAlign: 'middle' }}
      xmlns="http://www.w3.org/2000/svg"
    >
      {PIXEL_MAP.map((row, y) => 
        row.split('').map((char, x) => {
          if (char === '.') return null;
          return (
            <rect 
              key={`${x}-${y}`} 
              x={x} 
              y={y} 
              width={1} 
              height={1} 
              fill={colors[char]} 
            />
          );
        })
      )}
    </svg>
  );
}
