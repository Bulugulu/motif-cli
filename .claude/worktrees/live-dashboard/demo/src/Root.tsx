import React from "react";
import { Composition } from "remotion";
import { MotifDemo, DURATION_IN_FRAMES } from "./MotifDemo";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="MotifDemo"
      component={MotifDemo}
      durationInFrames={DURATION_IN_FRAMES}
      fps={30}
      width={800}
      height={500}
    />
  );
};
