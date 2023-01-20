module {
  desc: "summarizes a step/state via key domain object info and counts of other log data.",
  input: "object(<state>)",
  returns: "object()"
};

# ----

{
  insertIdCount: .insertIds | length,
  traceCount: .traces | length,
  taskCount: .tasks | length,
  pubSubMessageIdCount: .pubSubMessageIds | length,
  #
  posts: .posts,
  recipes: .recipes,
  recipeCollections: .recipeCollections,
  postsCount: .posts | length,
  recipesCount: .recipes | length,
  recipeCollectionsCount: .recipeCollections | length,
}
