# Other Configuration Items

The following items may configured in `config.json` but are usually supplied by
he LMS plugin when it asks for mixes:

{
 "essentia":{
  "bpm":20,
  "attr":0.4,
  "weight":0.0
 }
}

* `essentia.bpm` Specify max BPM difference when filtering tracks.
* `essentia.attr` Specify max difference in Essentia attributes. For each seed
attribute that is in the range 0.8 .. 1.0 a candidate must be in the range
0.8-`essentia.attr` .. 1.0, and for each attribute in the range 0.0 .. 0.2 a
candidate must be in the range 0.0 .. 0.2+`essentia.attr`
* `essentia.weight` By default Musly is used for similarity score, and Essentia
is used to filter tracks. However, if you set `essentia.weight` to higher than
0.0 (and less than or equal to 1.0) then Essentia can also be used to score
similarity based upon the Essentia attributes. This value then configures the
percentage give to each metric. e.g. an `essentia.weight` of 0.4 will cause the
similarity score to be base 60% Musly 40% Essentia.
