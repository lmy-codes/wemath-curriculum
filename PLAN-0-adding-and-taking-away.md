# Packet 0: Adding and Taking Away (within 9)

This packet comes before Ten Buddies. It teaches adding and taking away with pictures of real things, for kids who are not yet ready for ten-frames.

## Research

- **Join and separate stories come first.** Cognitively Guided Instruction (CGI) sorts early addition and subtraction into story types. Kindergarten starts with:
  - *join, result unknown*: "you have 3, you get 2 more"
  - *separate, result unknown*: "you have 3, I eat 1"
- **Kids model each number directly.** Kids solve these by acting them out with one object for each thing. Teaching starts with acting out stories, then counters, then drawings ([Relay: direct models](https://relay.libguides.com/math-interventions/direct-models), [Virginia K plan](https://doe.virginia.gov/home/showpublisheddocument/16396/638037041609330000), [CGI transcript, ESC-20](https://onlineprograms.esc20.net/testing/CGI-Portfolio/story_content/external_files/CGI%20Transcript.pdf)).
- **What the standards ask.** K.OA.1 and K.OA.2 ask kids to represent and solve add/subtract word problems within 10 using objects or drawings. K.OA.5 asks for fluency within 5. That supports two steps: **within 5 first, then up to 9** ([Utah K.OA core guide](https://schools.utah.gov/curr/mathematics/_mathematics_/_core/_math_core_guides_tab_/CoreGuidesKindergartenOperationsAlgebraic.pdf)).
- **Cross out, then count what's left.** For taking away, kids cross out the things that leave and count what is left. A common next task is to draw circles and cross them out ([CPALMS K.OA.1 access point](https://www.cpalms.org/PreviewAccessPoint/Export/15585), [Connecticut K unit 4](https://test-cd.ct.gov/-/media/sde/math/units/k/kindergarten_math_unit_4.doc)).
- **Signs come after the action makes sense.** Kids act out and draw first. The + and − signs are introduced after that.

## How the packet removes help

1. Pictures of both groups, then count them all (within 5).
2. Pictures to cross out (within 5).
3. Picture story problems (within 5). Each story is read aloud.
4. Put together up to 9. Groups sit in rows of five, like a ten-frame, with a light ring around each group.
5. Take away from up to 9.
6. Draw more: kids draw the circles for the ones being added.
7. Picture stories up to 9. Kids decide the sign and write the whole number sentence. The sign goes in a circle, so it can't be read as a digit.
8. Write the number sentence from a picture.
9. Draw to solve: no picture, kids draw their own circles.
10. No help, grouped by kind of question: adding to 5, taking away from 5, adding to 9, taking away from 9, mixed.
11. Word problems with no picture: kids draw their own.

The packet has 141 problems on 15 pages.

## Rules specific to this packet

- **Facts can repeat in pictures, but not as plain problems.** The same fact can come back in a different picture (3 gummy bears − 1, then 3 cupcakes − 1). That repetition is what builds retention. Plain no-help problems never repeat.
- **Leave the facts later packets own.** The plain problems skip the facts that later packets ask as plain problems. Packet 6 owns doubles and near doubles (2 + 1, 3 + 2, 4 + 4 …), and packet 1 owns pairs that make 10. Pictures of those facts are fine.
- **Sums stay at 9 or less.** Making 10 is the next packet, Ten Buddies.
- **Answers always go in the answer spot.** The one exception is "write the number sentence", where kids copy every number from the picture.

## Story bank

The 17 objects below already have pictures in `build_worksheets.py` (`icon()` and `STORY_BANK`). Each one has an "add" line and a "take away" line. The tool builds the full story, for example "You have 3 gummy bears. I eat 1 of them. How many are left?"

| Object | Start | Add | Take away |
|---|---|---|---|
| gummy bear | You have 3 gummy bears. | I give you 2 more. | I eat 1 of them. |
| apple | You have 4 apples. | You pick 2 more. | You eat 3. |
| cookie | There are 5 cookies on a plate. | Mom bakes 2 more. | You eat 2. |
| balloon | You have 7 balloons. | You get 2 more. | 2 pop! |
| fish | 3 fish swim in a pond. | 2 more swim in. | 2 swim away. |
| star | You draw 4 stars. | You draw 3 more. | You erase 1. |
| cupcake | There are 6 cupcakes. | Dad makes 2 more. | Your friends eat 3. |
| flower | 5 flowers grow in a garden. | 2 more grow. | You pick 4. |
| ladybug | 5 ladybugs sit on a leaf. | 3 more land. | 4 fly away. |
| egg | A nest has 6 eggs. | The bird lays 1 more. | 4 hatch. |
| bird | 4 birds sit in a tree. | 3 more fly in. | 2 fly away. |
| frog | 4 frogs sit on a log. | 4 more hop on. | 3 hop off. |
| leaf | 9 leaves are on the ground. | 2 more fall. | The wind blows 4 away. |
| crayon | You have 6 crayons. | You find 2 more. | 2 break. |
| car | 6 cars are parked. | 3 more park. | 4 drive away. |
| duck | 7 ducks swim in a pond. | 1 more swims over. | 5 waddle away. |
| candy | You have 9 candies. | Grandma gives you 2 more. | You share 6 with a friend. |

### More stories to draw next (not drawn yet)

Each would need a new picture (about 20 lines of drawing code each).

- **Food:**
  - strawberries: pick / eat
  - grapes: get / eat
  - pizza slices: bake / eat
  - carrots: pull from the garden / the bunny eats
  - pretzels: get / share
  - muffins: bake / sell
- **Animals:**
  - bunnies: hop in / hop away
  - bees: buzz over / fly home
  - butterflies: land / fly off
  - puppies: run in / go home
  - ants: march in / march away
  - chicks: hatch / run off
  - turtles: crawl up / swim off
- **Things kids use:**
  - blocks: build / knock down
  - marbles: find / roll away
  - stickers: get / give away
  - pencils: find / break
  - toy cars: get / lend
  - books: borrow / return
- **Outside:**
  - snowballs: make / melt
  - bubbles: blow / pop
  - kites: fly up / come down
  - shells: find / wash away
  - raindrops: fall / dry up
  - acorns: the squirrel finds / the squirrel eats
- **Party:**
  - candles: light / blow out
  - presents: get / open
  - hats: hand out / fall off
  - cups of juice: pour / drink

**Later (other CGI types):** "How many more?" (compare) and "Some are red, some are blue" (part-part-whole). Story types where the start or the change is unknown go with packet 11, Missing Numbers.
