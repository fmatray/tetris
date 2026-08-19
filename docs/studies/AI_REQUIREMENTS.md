# AI Feature Requirements

**Vision**: Develop an AI agent capable of mastering Tetris by learning from experience, optimizing piece placement for long-term survival, and executing complex maneuvers to maintain a clean board.
**Success Criteria**: The AI must be capable of achieving a score > 10,000 within 10,000 episodes of training.

### Must Have
- **Complete Control Set**: Must handle left/right movement, clockwise and counter-clockwise rotations.
- **Efficient Placement**: Must utilize both hard drops (instant) and soft drops (controlled descent).
- **Advanced Maneuvers**: Must be able to slide pieces under overhangs and utilize wall kicks (SRS) to rotate in confined spaces.
- **Strategic Foresight**: Must evaluate the current move based on the next upcoming piece, with 7-bag or truly random generator.
- **Knowledge Persistence**: Must be able to save and load its learned state to resume training or play.
- **User Configuration**: Must allow the user to customize AI behavior and training settings.
- **Performance Tracking**: Must display key metrics (e.g., survival time, average score, and reward trends) to verify improvement over time.
- **Accelerated Simulation**: Must support training at speeds significantly faster than real-time.

### Should Have
- **Guided Learning**: Must support a training curriculum (e.g., mastering simple pieces before complex ones).
- **Version Benchmarking**: Must provide a way to compare the performance of different AI iterations.
- **Decision Visualization**: Must visually indicate candidate placements being evaluated, the chosen move, and the confidence/value assigned to it.
- **Game Auditing**: Must provide a way to record and replay AI games to analyze specific decision-making failures.
- **T-Spin Execution**: Must be able to identify and execute T-Spin maneuvers to optimize board clearing.
- **Lock Delay Exploitation**: Must be able to utilize lock-down delay to perform advanced placements and tucks.

### Could Have
- **Competitive Play**: Must be able to play against other AI agents or a human user in real-time.
- **Variant Adaptability**: Must be able to adapt to different board sizes or dimensions.
- **Standardized Evaluation**: Must track performance against a set of fixed piece sequences (seeds) for objective scoring.

### Won't Have
- **External Infrastructure**: Distributed or cloud-based training.
- **General Intelligence**: Ability to play any game other than Tetris.
- **Visual Input**: Processing raw screen pixels (uses direct game state).
