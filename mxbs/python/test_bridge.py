"""MxBS Bridge smoke test."""
from mxbs_bridge import MxBSBridge


def main():
    with MxBSBridge(":memory:") as mxbs:
        # 1. store
        cell_id = mxbs.store(
            owner=1, text="test memory",
            from_id=1, turn=1,
            group_bits=0x01, mode=0o744, price=100,
            features=[200, 100, 50, 150, 80, 60, 120, 140, 90, 50, 160, 100, 70, 130, 90, 110],
        )
        print(f"  store: cell_id={cell_id}")

        # 2. get
        cell = mxbs.get(cell_id)
        print(f"  get: owner={cell['owner']}, text={cell['text']}")

        # 3. search
        results = mxbs.search(
            [200, 100, 50, 150, 80, 60, 120, 140, 90, 50, 160, 100, 70, 130, 90, 110],
            viewer_id=1, viewer_groups=0x01,
            current_turn=1, limit=5,
        )
        print(f"  search: {len(results)} results")
        for r in results:
            print(f"    score={r['effective_score']:.4f} text={r['text']}")

        # 4. stats
        stats = mxbs.stats()
        print(f"  stats: {stats}")

        # 5. deferred scoring
        cell_id2 = mxbs.store(
            owner=2, text="unscored memory",
            from_id=2, turn=2,
            group_bits=0x03, mode=0o744, price=80,
            features=None,
        )
        unscored = mxbs.get_unscored()
        print(f"  get_unscored: {len(unscored)} cells")

        ok = mxbs.set_features(cell_id2, [100] * 16)
        print(f"  set_features: {ok}")

        # 6. dream
        dreams = mxbs.dream(viewer_id=1, viewer_groups=0x01, current_turn=10)
        print(f"  dream: {len(dreams)} results")

        # 7. reinforce
        ok = mxbs.reinforce(cell_id, 5.0)
        print(f"  reinforce: {ok}")

        # 8. inspire
        related = mxbs.inspire(cell_id, limit=5, viewer_id=1, viewer_groups=0x01)
        print(f"  inspire: {len(related)} results")

        # 9. update meta
        ok = mxbs.update_meta(cell_id, '{"tag":"test"}', requester=1, req_groups=0)
        print(f"  update_meta: {ok}")
        cell_after = mxbs.get(cell_id)
        print(f"  meta after: {cell_after['meta']}")

        # 10. delete
        ok = mxbs.delete(cell_id2, requester=2, req_groups=0x03)
        print(f"  delete: {ok}")

        final_stats = mxbs.stats()
        print(f"  final stats: {final_stats}")

        print("\nAll smoke tests passed!")


if __name__ == "__main__":
    main()
