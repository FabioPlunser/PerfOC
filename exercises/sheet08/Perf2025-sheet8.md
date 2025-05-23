# A) Vulkan-ValidationLayers PR

The code was experiencing false sharing 
issues in multithreaded scenarios, where multiple 
threads were accessing different ObjectUseData instances 
that could end up on the same cache line. This was causing 
unnecessary cache invalidation and performance degradation.

The fix replaces manual padding bytes with proper memory 
alignment using alignas and get_hardware_destructive_interference_size(). Key changes:
```cpp
constexpr std::size_t get_hardware_destructive_interference_size() { return 64; }
```
Why 64?
The size of a cache line on most modern CPUs is 64 bytes.


```cpp
- padding[0] = 0; 
+class alignas(get_hardware_destructive_interference_size()) ObjectUseData
```


- Ensures ObjectUseData instances are aligned to cache line boundaries
- Prevents false sharing between threads accessing different instances
- Cleaner implementation than manual padding bytes

As noted in TODO comment, this should be updated to use C++20's feature 
`std::hardware_destructive_interference_size`

# B) 
Summary of Commit 
Sevlete use linked lists for each blocks https://github.com/sveltejs/svelte/pull/11107

## Comment From Rich Harris:
This replaces the current implementation of `{#each ...}` blocks with a linked list implementation. 

What this means is that rather than constantly replacing `state.items`(which is prone to race conditions that are tricky to accommodate), we update the linked list in place as the value changes. As such, it's easy to handle things like aborted outros in the middle of the list without them being re-appended.

The hard part of list reconciliation algorithms is minimising moves in a direction-agnostic way. For example, if a list changes from `ABCDE` to `BCDEA`, this can easily be accomplished by stashing the existing A, skipping over `BCDE` (because everything matches), then grabbing A from the stash and moving it to the end.

## Code Changes
```js
export type EachState = {
	/** flags */
	flags: number;
	- /** items */
	- items: EachItem[];
	+ /** a key -> item lookup */
	+ items: Map<any, EachItem>;
	+ /** head of the linked list of items */
	+ next: EachItem | null;
};
```
```js
export type EachItem = {
	i: number | Source<number>;
	/** key */
	k: unknown;
	+ prev: EachItem | EachState;
	+ next: EachItem | null;
};
```

```js
/** @type {typeof a_items} */
	var b_items = Array(b);
	/** @type {Set<import('#client').EachItem>} */
	var seen = new Set();
```


The changes in the pull request make a transition from Array-based operations to a Linked List structure in the each.js file. Key highlights include:

- Introduction of link function: This function is used to manage relationships between nodes, replacing array indexing operations.
```js
function link(prev, next) {
    prev.next = next;
    if (next !== null) next.prev = prev;
}
```
Efficient linking: Nodes are linked using prev and next pointers, 
facilitating traversal and modification of the data structure.

- Node creation
```js
function create_item(anchor, prev, next, value, key, index, render_fn, flags) {
    var item = {
        i: index,
        v: value,
        k: key,
        prev,
        next,
        e: branch(() => render_fn(anchor, value, index))
    };
    prev.next = item;
    if (next !== null) next.prev = item;
    return item;
}
```

Avoiding mutations: Methods like move and get_first_child are used to maintain the immutability of certain operations, crucial for Linked List integrity.
Usage of matched and stashed: These collections are updated to align with Linked List semantics, instead of relying on array-specific operations.

These changes optimize the data structure for scenarios requiring frequent insertions and deletions, leveraging the strengths of a Linked List.

