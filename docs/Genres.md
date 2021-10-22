# Genre grouping

Genres can configured via the `genres` section of `config.json`, using the
following syntax:

```
{
 "genres:[
  [ "Rock", "Hard Rock", "Metal"],
  [ "Pop", "Dance", "R&B"]
 ]
}
```

If a seed track has `Hard Rock` as its genre, then only tracks with `Rock`,
`Hard Rock`, or `Metal` will be allowed. If a seed track has a genre that is not
listed here then any track returned by Musly, that does not contain any genre
listed here, will be considered acceptable. Therefore, if seed is `Pop` then
a `Hard Rock` track would not be considered.

*NOTE* Genre groups can now be configured directly in the [LMS Music Similarity Plugin](https://github.com/CDrummond/lms-musicsimilarity),
therfore there is no need to add these to `config.json` Therefore, this section
is no longer required.

